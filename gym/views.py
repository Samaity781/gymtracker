"""
gym/views.py
Epic 3-5 views + CR1 (search), CR2 (ranking), CR3 (promotions).

Views are kept thin by delegating to:
  - search_service.py    — filter/search logic (CR1)
  - ranking_service.py   — intelligent ordering (CR2)
  - promotion_service.py — impression/click tracking (CR3)
  - reviews app          — aggregate ratings injected on detail pages (CR4)
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from .forms import CategoryForm, ClassSearchForm, EquipmentSearchForm, GymEquipmentForm, WorkoutClassForm
from .models import GymEquipment, WorkoutCategory, WorkoutClass
from . import ranking_service, search_service, promotion_service


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """
    CR3: Featured items record impressions when rendered here.
    CR2: Featured items appear first; upcoming is the secondary sort.
    """
    upcoming_classes = (
        WorkoutClass.objects
        .filter(is_active=True, start_time__gte=timezone.now())
        .order_by('-is_featured', 'start_time')
        .select_related('category')[:6]
    )
    featured_equipment = (
        GymEquipment.objects
        .filter(is_active=True, is_featured=True)
        .select_related('category')[:4]
    )
    categories = WorkoutCategory.objects.filter(is_active=True)

    # CR3: record impressions for all featured items on this page
    featured_classes = [c for c in upcoming_classes if c.is_featured]
    all_featured = list(featured_classes) + list(featured_equipment)
    if all_featured:
        promotion_service.record_impressions(all_featured, request.user, source_page='dashboard')

    return render(request, 'gym/dashboard.html', {
        'upcoming_classes': upcoming_classes,
        'featured_equipment': featured_equipment,
        'categories': categories,
    })


# ─── CR3: Featured item click tracking ───────────────────────────────────────

@login_required
def featured_click(request, item_type, pk):
    """
    Thin redirect that records a CR3 click before forwarding to the detail view.
    This keeps tracking logic completely out of the detail views themselves.
    """
    if item_type == 'class':
        item = get_object_or_404(WorkoutClass, pk=pk)
        if item.is_featured:
            promotion_service.record_click(item, request.user, source_page='dashboard')
        return redirect('gym:class_detail', pk=pk)
    item = get_object_or_404(GymEquipment, pk=pk)
    if item.is_featured:
        promotion_service.record_click(item, request.user, source_page='dashboard')
    return redirect('gym:equipment_detail', pk=pk)


# ─── Workout Classes ──────────────────────────────────────────────────────────

@login_required
def class_list(request):
    """
    FR-08 / FR-09 / CR1: Combined filters via search_service.
    CR2: Admin ranking toggle via ?ranking=smart|default.
    FR-20: All filter state preserved in query string automatically (GET form).
    """
    form = ClassSearchForm(request.GET or None)
    queryset = WorkoutClass.objects.filter(is_active=True).select_related('category')

    active_filter_count = 0
    if form.is_valid():
        queryset = search_service.apply_class_filters(queryset, form.cleaned_data)
        active_filter_count = search_service.get_active_filter_count(form.cleaned_data)

    ranking_mode = request.GET.get('ranking', 'default')
    show_scores = False
    if ranking_mode == 'smart' and request.user.is_admin_role:
        classes = ranking_service.rank_classes(queryset)
        show_scores = True
    else:
        classes = queryset.order_by('-is_featured', 'start_time')
        ranking_mode = 'default'

    filter_qs = search_service.build_filter_querystring(request.GET)
    categories = WorkoutCategory.objects.filter(is_active=True)
    return render(request, 'gym/class_list.html', {
        'form': form,
        'classes': classes,
        'categories': categories,
        'ranking_mode': ranking_mode,
        'show_scores': show_scores,
        'active_filter_count': active_filter_count,
        'filter_qs': filter_qs,
    })


@login_required
def class_detail(request, pk):
    workout_class = get_object_or_404(WorkoutClass, pk=pk, is_active=True)

    # CR2: increment view count (used as popularity signal in ranking)
    WorkoutClass.objects.filter(pk=pk).update(view_count=workout_class.view_count + 1)

    user_booking = None
    from bookings.models import Booking
    if request.user.is_authenticated:
        user_booking = Booking.objects.filter(
            user=request.user, workout_class=workout_class
        ).exclude(status=Booking.Status.CANCELLED).first()

    # CR4: reviews context
    from reviews.models import Review
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(WorkoutClass)
    approved_reviews = (
        Review.objects
        .filter(content_type=ct, object_id=pk, status=Review.Status.APPROVED)
        .select_related('user').order_by('-created_at')
    )
    aggregate = Review.get_aggregate(ct, pk)
    user_review = (
        Review.objects.filter(content_type=ct, object_id=pk, user=request.user).first()
        if request.user.is_authenticated else None
    )
    can_review = (
        request.user.is_authenticated
        and not user_review
        and Booking.objects.filter(
            user=request.user, workout_class=workout_class,
            status=Booking.Status.ATTENDED,
        ).exists()
    )

    return render(request, 'gym/class_detail.html', {
        'workout_class': workout_class,
        'user_booking': user_booking,
        'approved_reviews': approved_reviews,
        'aggregate': aggregate,
        'user_review': user_review,
        'can_review': can_review,
        'content_type_id': ct.pk,
    })


# ─── Admin: Classes CRUD ──────────────────────────────────────────────────────

@admin_required
def admin_class_list(request):
    classes = WorkoutClass.objects.all().select_related('category').order_by('-start_time')
    return render(request, 'gym/admin/class_list.html', {'classes': classes})


@admin_required
def admin_class_create(request):
    form = WorkoutClassForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Workout class created.")
        return redirect('gym:admin_class_list')
    return render(request, 'gym/admin/class_form.html', {'form': form, 'action': 'Create'})


@admin_required
def admin_class_edit(request, pk):
    workout_class = get_object_or_404(WorkoutClass, pk=pk)
    form = WorkoutClassForm(request.POST or None, request.FILES or None, instance=workout_class)
    if form.is_valid():
        form.save()
        messages.success(request, "Workout class updated.")
        return redirect('gym:admin_class_list')
    return render(request, 'gym/admin/class_form.html', {
        'form': form, 'action': 'Edit', 'workout_class': workout_class,
    })


@admin_required
@require_POST
def admin_class_toggle_active(request, pk):
    workout_class = get_object_or_404(WorkoutClass, pk=pk)
    workout_class.is_active = not workout_class.is_active
    workout_class.save(update_fields=['is_active'])
    messages.success(request, f'"{workout_class.name}" {"activated" if workout_class.is_active else "deactivated"}.')
    return redirect('gym:admin_class_list')


@admin_required
@require_POST
def admin_class_delete(request, pk):
    workout_class = get_object_or_404(WorkoutClass, pk=pk)
    name = workout_class.name
    workout_class.delete()
    messages.success(request, f'"{name}" deleted.')
    return redirect('gym:admin_class_list')


# ─── Equipment views ──────────────────────────────────────────────────────────

@login_required
def equipment_list(request):
    """CR1: Equipment search with text and category filters."""
    form = EquipmentSearchForm(request.GET or None)
    queryset = GymEquipment.objects.filter(is_active=True).select_related('category')

    active_filter_count = 0
    if form.is_valid():
        queryset = search_service.apply_equipment_filters(queryset, form.cleaned_data)
        active_filter_count = search_service.get_active_filter_count(form.cleaned_data)

    ranking_mode = request.GET.get('ranking', 'default')
    show_scores = False
    if ranking_mode == 'smart' and request.user.is_admin_role:
        equipment = ranking_service.rank_equipment(queryset)
        show_scores = True
    else:
        equipment = queryset.order_by('-is_featured', 'name')
        ranking_mode = 'default'

    filter_qs = search_service.build_filter_querystring(request.GET)
    categories = WorkoutCategory.objects.filter(is_active=True)
    return render(request, 'gym/equipment_list.html', {
        'form': form,
        'equipment': equipment,
        'categories': categories,
        'ranking_mode': ranking_mode,
        'show_scores': show_scores,
        'active_filter_count': active_filter_count,
        'filter_qs': filter_qs,
    })


@login_required
def equipment_detail(request, pk):
    equipment = get_object_or_404(GymEquipment, pk=pk, is_active=True)
    GymEquipment.objects.filter(pk=pk).update(view_count=equipment.view_count + 1)

    from reviews.models import Review
    from django.contrib.contenttypes.models import ContentType
    from bookings.models import Booking
    ct = ContentType.objects.get_for_model(GymEquipment)
    approved_reviews = (
        Review.objects
        .filter(content_type=ct, object_id=pk, status=Review.Status.APPROVED)
        .select_related('user').order_by('-created_at')
    )
    aggregate = Review.get_aggregate(ct, pk)
    user_review = (
        Review.objects.filter(content_type=ct, object_id=pk, user=request.user).first()
        if request.user.is_authenticated else None
    )
    can_review = (
        request.user.is_authenticated
        and not user_review
        and Booking.objects.filter(
            user=request.user, equipment=equipment,
            status=Booking.Status.ATTENDED,
        ).exists()
    )

    return render(request, 'gym/equipment_detail.html', {
        'equipment': equipment,
        'approved_reviews': approved_reviews,
        'aggregate': aggregate,
        'user_review': user_review,
        'can_review': can_review,
        'content_type_id': ct.pk,
    })


@admin_required
def admin_equipment_list(request):
    equipment = GymEquipment.objects.all().select_related('category').order_by('name')
    return render(request, 'gym/admin/equipment_list.html', {'equipment': equipment})


@admin_required
def admin_equipment_create(request):
    form = GymEquipmentForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Equipment item created.")
        return redirect('gym:admin_equipment_list')
    return render(request, 'gym/admin/equipment_form.html', {'form': form, 'action': 'Create'})


@admin_required
def admin_equipment_edit(request, pk):
    equipment = get_object_or_404(GymEquipment, pk=pk)
    form = GymEquipmentForm(request.POST or None, request.FILES or None, instance=equipment)
    if form.is_valid():
        form.save()
        messages.success(request, "Equipment updated.")
        return redirect('gym:admin_equipment_list')
    return render(request, 'gym/admin/equipment_form.html', {
        'form': form, 'action': 'Edit', 'equipment': equipment,
    })


@admin_required
@require_POST
def admin_equipment_toggle_active(request, pk):
    equipment = get_object_or_404(GymEquipment, pk=pk)
    equipment.is_active = not equipment.is_active
    equipment.save(update_fields=['is_active'])
    messages.success(request, f'"{equipment.name}" {"activated" if equipment.is_active else "deactivated"}.')
    return redirect('gym:admin_equipment_list')


@admin_required
@require_POST
def admin_equipment_delete(request, pk):
    equipment = get_object_or_404(GymEquipment, pk=pk)
    name = equipment.name
    equipment.delete()
    messages.success(request, f'"{name}" deleted.')
    return redirect('gym:admin_equipment_list')


# ─── Categories ───────────────────────────────────────────────────────────────

@admin_required
def admin_category_list(request):
    categories = WorkoutCategory.objects.all()
    return render(request, 'gym/admin/category_list.html', {'categories': categories})


@admin_required
def admin_category_create(request):
    form = CategoryForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        return redirect('gym:admin_category_list')
    return render(request, 'gym/admin/category_form.html', {'form': form, 'action': 'Create'})


@admin_required
def admin_category_edit(request, pk):
    category = get_object_or_404(WorkoutCategory, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if form.is_valid():
        form.save()
        messages.success(request, "Category updated.")
        return redirect('gym:admin_category_list')
    return render(request, 'gym/admin/category_form.html', {
        'form': form, 'action': 'Edit', 'category': category,
    })


@admin_required
@require_POST
def admin_category_delete(request, pk):
    category = get_object_or_404(WorkoutCategory, pk=pk)
    name = category.name
    category.delete()
    messages.success(request, f'Category "{name}" deleted.')
    return redirect('gym:admin_category_list')


# ─── CR3: Admin promotions analytics ─────────────────────────────────────────

@admin_required
def admin_promotions(request):
    """CR3 analytics: impressions, clicks, CTR for all featured items."""
    analytics = promotion_service.get_promotion_analytics()
    return render(request, 'gym/admin/promotions.html', {'analytics': analytics})
