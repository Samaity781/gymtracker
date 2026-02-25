"""
reviews/views.py
CR4: Review submission and admin moderation workflow.

Member flow:
  submit_review  → creates a PENDING review; redirect back to the item.
  edit_review    → only for PENDING reviews (not yet moderated).

Admin flow:
  admin_review_list     → all reviews with status filter tabs.
  admin_moderate_review → approve or hide, with optional note.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from .forms import ModerationForm, ReviewForm
from .models import Review


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_item_and_redirect(content_type_id, object_id):
    """Resolve a content type + object id to an item and its detail URL."""
    from gym.models import GymEquipment, WorkoutClass

    ct   = get_object_or_404(ContentType, pk=content_type_id)
    item = ct.get_object_for_this_type(pk=object_id)

    model_class = ct.model_class()
    if model_class == WorkoutClass:
        from django.urls import reverse
        redirect_url = reverse('gym:class_detail', args=[object_id])
    elif model_class == GymEquipment:
        from django.urls import reverse
        redirect_url = reverse('gym:equipment_detail', args=[object_id])
    else:
        redirect_url = '/'

    return item, redirect_url


# ─── Member: submit review ────────────────────────────────────────────────────

@login_required
@require_POST
def submit_review(request, content_type_id, object_id):
    """
    POST-only: create a new PENDING review for an item.
    Eligibility check (ATTENDED booking) is enforced here — not just in the
    template — so it cannot be bypassed by direct POST.
    """
    item, redirect_url = _get_item_and_redirect(content_type_id, object_id)
    ct = ContentType.objects.get(pk=content_type_id)

    # Guard: one review per user per item
    if Review.objects.filter(content_type=ct, object_id=object_id, user=request.user).exists():
        messages.warning(request, "You have already submitted a review for this item.")
        return redirect(redirect_url)

    # Guard: must have an ATTENDED booking
    from bookings.models import Booking
    from gym.models import WorkoutClass, GymEquipment

    model_class = ct.model_class()
    has_attended = False
    if model_class == WorkoutClass:
        has_attended = Booking.objects.filter(
            user=request.user, workout_class_id=object_id,
            status=Booking.Status.ATTENDED,
        ).exists()
    elif model_class == GymEquipment:
        has_attended = Booking.objects.filter(
            user=request.user, equipment_id=object_id,
            status=Booking.Status.ATTENDED,
        ).exists()

    if not has_attended:
        messages.error(request, "You can only review an item after attending or using it.")
        return redirect(redirect_url)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.content_type = ct
        review.object_id    = object_id
        review.user         = request.user
        review.save()
        messages.success(request, "Your review has been submitted and is awaiting moderation.")
    else:
        for error in form.errors.values():
            messages.error(request, error.as_text())

    return redirect(redirect_url)


# ─── Member: edit own review ──────────────────────────────────────────────────

@login_required
def edit_review(request, pk):
    review = get_object_or_404(Review, pk=pk, user=request.user)
    _, redirect_url = _get_item_and_redirect(review.content_type_id, review.object_id)

    if not review.is_editable:
        messages.warning(request, "This review has already been moderated and cannot be edited.")
        return redirect(redirect_url)

    form = ReviewForm(request.POST or None, instance=review)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Your review has been updated.")
        return redirect(redirect_url)

    return render(request, 'reviews/edit_review.html', {'form': form, 'review': review})


# ─── Admin: review list ───────────────────────────────────────────────────────

@admin_required
def admin_review_list(request):
    """All reviews across all items, filterable by status tab."""
    status_filter = request.GET.get('status', '')
    queryset = Review.objects.select_related('user', 'content_type').order_by('-created_at')

    if status_filter in (Review.Status.PENDING, Review.Status.APPROVED, Review.Status.HIDDEN):
        queryset = queryset.filter(status=status_filter)

    counts = {
        'all':     Review.objects.count(),
        'pending': Review.objects.filter(status=Review.Status.PENDING).count(),
        'approved': Review.objects.filter(status=Review.Status.APPROVED).count(),
        'hidden':  Review.objects.filter(status=Review.Status.HIDDEN).count(),
    }

    return render(request, 'reviews/admin/review_list.html', {
        'reviews':       queryset,
        'status_filter': status_filter,
        'counts':        counts,
    })


# ─── Admin: moderate a review ─────────────────────────────────────────────────

@admin_required
def admin_moderate_review(request, pk):
    """
    GET: show the review with a moderation form.
    POST: approve or hide depending on the action button submitted.
    """
    review = get_object_or_404(Review, pk=pk)
    _, redirect_url = _get_item_and_redirect(review.content_type_id, review.object_id)

    if request.method == 'POST':
        form = ModerationForm(request.POST)
        if form.is_valid():
            note   = form.cleaned_data.get('moderation_note', '')
            action = request.POST.get('action')

            if action == 'approve':
                review.approve(request.user, note=note)
                messages.success(request, f"Review by {review.user.email} approved.")
            elif action == 'hide':
                review.hide(request.user, note=note)
                messages.success(request, f"Review by {review.user.email} hidden.")
            else:
                messages.error(request, "Unknown action.")

            return redirect('reviews:admin_review_list')
    else:
        form = ModerationForm(initial={'moderation_note': review.moderation_note})

    return render(request, 'reviews/admin/moderate_review.html', {
        'review': review,
        'form':   form,
    })
