"""
tests/test_cr_implementations.py
CR1–CR4 test suite.

Covers:
  CR1 – Advanced search: combined filters, date range, availability, validation.
  CR2 – Intelligent ranking: score components, ordering correctness.
  CR3 – Promotional placement: impression/click recording, CTR calculation,
          click-tracking redirect view, analytics aggregation.
  CR4 – Reviews/ratings: one-review constraint, moderation workflow (PENDING →
          APPROVED / HIDDEN), aggregate calculation, eligibility guard.
"""

from datetime import date, timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from gym.models import GymEquipment, PromotionEvent, WorkoutCategory, WorkoutClass
from gym import ranking_service, search_service, promotion_service
from reviews.models import Review


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_user(email='member@test.com', role=User.Role.MEMBER):
    return User.objects.create_user(
        email=email, password='testpass123',
        first_name='Test', last_name='User', role=role,
    )

def make_admin(email='admin@test.com'):
    return make_user(email=email, role=User.Role.ADMIN)

def make_category(name='Spin'):
    return WorkoutCategory.objects.create(name=name)

def make_class(name='Morning Spin', category=None, days_ahead=1,
               capacity=20, booked=0, featured=False, active=True):
    cat = category or make_category(name)
    cls = WorkoutClass.objects.create(
        name=name,
        category=cat,
        start_time=timezone.now() + timedelta(days=days_ahead),
        duration_minutes=60,
        capacity=capacity,
        booked_count=booked,
        is_active=active,
        is_featured=featured,
        instructor='Test Instructor',
    )
    return cls

def make_equipment(name='Rowing Machine', category=None, featured=False):
    cat = category or make_category(name)
    return GymEquipment.objects.create(
        name=name, category=cat, capacity=2,
        is_active=True, is_featured=featured,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  CR1: Advanced Search
# ═══════════════════════════════════════════════════════════════════════════════

class AdvancedSearchServiceTests(TestCase):
    """Unit tests for gym/search_service.py — exercises filters in isolation."""

    def setUp(self):
        self.cat_spin  = make_category('Spin')
        self.cat_yoga  = make_category('Yoga')
        self.spin_am   = make_class('Morning Spin',  category=self.cat_spin, days_ahead=1)
        self.spin_pm   = make_class('Evening Spin',  category=self.cat_spin, days_ahead=2)
        self.yoga      = make_class('Flow Yoga',     category=self.cat_yoga, days_ahead=3)
        self.full_cls  = make_class('HIIT Blast',    capacity=10, booked=10, days_ahead=1)
        self.past_cls  = make_class('Old Yoga',      category=self.cat_yoga, days_ahead=-3)
        self.qs = WorkoutClass.objects.filter(is_active=True)

    # ── Text search ──────────────────────────────────────────────────────

    def test_text_search_by_name(self):
        result = search_service.apply_class_filters(self.qs, {'q': 'spin'})
        names = list(result.values_list('name', flat=True))
        self.assertIn('Morning Spin', names)
        self.assertIn('Evening Spin', names)
        self.assertNotIn('Flow Yoga', names)

    def test_text_search_by_instructor(self):
        result = search_service.apply_class_filters(self.qs, {'q': 'Test Instructor'})
        self.assertGreater(result.count(), 0)

    def test_text_search_case_insensitive(self):
        result = search_service.apply_class_filters(self.qs, {'q': 'YOGA'})
        names = list(result.values_list('name', flat=True))
        self.assertIn('Flow Yoga', names)

    def test_empty_query_returns_all_active(self):
        result = search_service.apply_class_filters(self.qs, {'q': ''})
        self.assertEqual(result.count(), self.qs.count())

    # ── Category filter (FR-08) ───────────────────────────────────────────

    def test_category_filter_excludes_other_category(self):
        result = search_service.apply_class_filters(
            self.qs, {'category': self.cat_spin}
        )
        for cls in result:
            self.assertEqual(cls.category, self.cat_spin)

    def test_category_filter_combined_with_text(self):
        result = search_service.apply_class_filters(
            self.qs, {'q': 'spin', 'category': self.cat_spin}
        )
        self.assertEqual(result.count(), 2)

    # ── Date range (CR1) ──────────────────────────────────────────────────

    def test_date_from_excludes_earlier_classes(self):
        tomorrow = (timezone.now() + timedelta(days=2)).date()
        result = search_service.apply_class_filters(self.qs, {'date_from': tomorrow})
        for cls in result:
            self.assertGreaterEqual(cls.start_time.date(), tomorrow)

    def test_date_to_excludes_later_classes(self):
        today = timezone.now().date()
        result = search_service.apply_class_filters(self.qs, {'date_to': today})
        for cls in result:
            self.assertLessEqual(cls.start_time.date(), today)

    # ── Availability filter (CR1) ─────────────────────────────────────────

    def test_available_only_excludes_full_classes(self):
        result = search_service.apply_class_filters(self.qs, {'available_only': True})
        for cls in result:
            self.assertFalse(cls.is_full, f"{cls.name} should not be full")

    def test_available_only_false_includes_full_classes(self):
        result = search_service.apply_class_filters(self.qs, {'available_only': False})
        ids = list(result.values_list('pk', flat=True))
        self.assertIn(self.full_cls.pk, ids)

    # ── Upcoming only (CR1) ───────────────────────────────────────────────

    def test_upcoming_only_excludes_past_classes(self):
        result = search_service.apply_class_filters(self.qs, {'upcoming_only': True})
        for cls in result:
            self.assertTrue(cls.is_upcoming)

    # ── Query string helper ───────────────────────────────────────────────

    def test_build_filter_querystring_excludes_pagination(self):
        params = {'q': 'spin', 'category': '2', 'page': '3', 'ranking': 'smart'}
        qs = search_service.build_filter_querystring(params)
        self.assertIn('q=spin', qs)
        self.assertNotIn('page=', qs)
        self.assertNotIn('ranking=', qs)

    def test_active_filter_count(self):
        data = {'q': 'spin', 'available_only': True, 'category': self.cat_spin}
        count = search_service.get_active_filter_count(data)
        self.assertEqual(count, 3)


# ═══════════════════════════════════════════════════════════════════════════════
#  CR2: Intelligent Ranking
# ═══════════════════════════════════════════════════════════════════════════════

class RankingServiceTests(TestCase):
    """Unit tests for gym/ranking_service.py."""

    def setUp(self):
        self.cat = make_category('HIIT')

    def test_featured_class_scores_higher_than_non_featured(self):
        featured     = make_class('Featured', category=self.cat, featured=True)
        non_featured = make_class('Plain',    category=self.cat, featured=False)
        self.assertGreater(ranking_service.score_class(featured),
                           ranking_service.score_class(non_featured))

    def test_available_class_scores_higher_than_full(self):
        available = make_class('Available', category=self.cat, capacity=20, booked=0)
        full      = make_class('Full',      category=self.cat, capacity=20, booked=20)
        self.assertGreater(ranking_service.score_class(available),
                           ranking_service.score_class(full))

    def test_popular_class_scores_higher_due_to_view_count(self):
        popular  = make_class('Popular', category=self.cat)
        popular.view_count    = 150
        popular.booking_count = 80
        popular.save(update_fields=['view_count', 'booking_count'])

        unpopular = make_class('Quiet', category=self.cat)
        self.assertGreater(ranking_service.score_class(popular),
                           ranking_service.score_class(unpopular))

    def test_imminent_class_scores_higher_than_distant(self):
        imminent = make_class('Soon', category=self.cat, days_ahead=1)
        distant  = make_class('Far',  category=self.cat, days_ahead=30)
        self.assertGreater(ranking_service.score_class(imminent),
                           ranking_service.score_class(distant))

    def test_score_is_normalised_to_0_100(self):
        cls = make_class(category=self.cat, featured=True)
        score = ranking_service.score_class(cls)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_rank_classes_returns_sorted_list(self):
        c1 = make_class('C1', category=self.cat, featured=True, days_ahead=1)
        c2 = make_class('C2', category=self.cat, featured=False, days_ahead=5)
        c3 = make_class('C3', category=self.cat, featured=False, days_ahead=2)
        qs = WorkoutClass.objects.filter(is_active=True)
        ranked = ranking_service.rank_classes(qs)
        # Featured c1 should be first
        self.assertEqual(ranked[0].pk, c1.pk)

    def test_ranked_objects_have_ranking_score_attribute(self):
        make_class(category=self.cat)
        qs = WorkoutClass.objects.filter(is_active=True)
        ranked = ranking_service.rank_classes(qs)
        for cls in ranked:
            self.assertTrue(hasattr(cls, 'ranking_score'))

    def test_score_breakdown_keys(self):
        cls = make_class(category=self.cat, featured=True)
        breakdown = ranking_service.get_score_breakdown(cls)
        self.assertIn('total_score', breakdown)
        self.assertIn('featured', breakdown)
        self.assertIn('view_count', breakdown)

    def test_equipment_score_is_0_to_100(self):
        eq = make_equipment(featured=True)
        score = ranking_service.score_equipment(eq)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class RankingViewToggleTests(TestCase):
    """Integration tests — admin can toggle ranking via query param."""

    def setUp(self):
        self.admin  = make_admin()
        self.member = make_user()
        self.client = Client()
        cat = make_category('Toggle')
        make_class('C1', category=cat, featured=True,  days_ahead=1)
        make_class('C2', category=cat, featured=False, days_ahead=2)

    def test_smart_ranking_requires_admin_role(self):
        """Members requesting smart ranking should silently receive default ordering."""
        self.client.force_login(self.member)
        response = self.client.get(reverse('gym:class_list') + '?ranking=smart')
        self.assertEqual(response.status_code, 200)
        # Context should not expose scores to members
        self.assertFalse(response.context['show_scores'])

    def test_admin_gets_smart_ranking_with_scores(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('gym:class_list') + '?ranking=smart')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_scores'])
        self.assertEqual(response.context['ranking_mode'], 'smart')

    def test_default_ranking_does_not_show_scores(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('gym:class_list') + '?ranking=default')
        self.assertFalse(response.context['show_scores'])


# ═══════════════════════════════════════════════════════════════════════════════
#  CR3: Promotional Placement
# ═══════════════════════════════════════════════════════════════════════════════

class PromotionServiceTests(TestCase):
    """Unit tests for gym/promotion_service.py."""

    def setUp(self):
        self.user     = make_user()
        self.cat      = make_category('Promo')
        self.cls      = make_class('Promo Class', category=self.cat, featured=True)
        self.equip    = make_equipment('Promo Machine', featured=True)

    def test_record_impressions_creates_events(self):
        promotion_service.record_impressions([self.cls, self.equip], self.user, 'dashboard')
        self.assertEqual(PromotionEvent.objects.count(), 2)

    def test_record_impressions_increments_counter(self):
        promotion_service.record_impressions([self.cls], self.user, 'dashboard')
        self.cls.refresh_from_db()
        self.assertEqual(self.cls.impression_count, 1)

    def test_record_impressions_accumulates_across_calls(self):
        promotion_service.record_impressions([self.cls], self.user, 'dashboard')
        promotion_service.record_impressions([self.cls], self.user, 'class_list')
        self.cls.refresh_from_db()
        self.assertEqual(self.cls.impression_count, 2)

    def test_record_click_creates_event(self):
        promotion_service.record_click(self.cls, self.user, 'dashboard')
        self.assertEqual(PromotionEvent.objects.filter(
            event_type=PromotionEvent.EventType.CLICK
        ).count(), 1)

    def test_record_click_increments_click_count(self):
        promotion_service.record_click(self.equip, self.user, 'dashboard')
        self.equip.refresh_from_db()
        self.assertEqual(self.equip.click_count, 1)

    def test_ctr_property_calculates_correctly(self):
        # Manually set counters to test the property
        WorkoutClass.objects.filter(pk=self.cls.pk).update(
            impression_count=100, click_count=25
        )
        self.cls.refresh_from_db()
        self.assertEqual(self.cls.ctr, 25.0)

    def test_ctr_zero_when_no_impressions(self):
        self.assertEqual(self.cls.ctr, 0.0)

    def test_record_impressions_empty_list_is_safe(self):
        promotion_service.record_impressions([], self.user, 'dashboard')
        self.assertEqual(PromotionEvent.objects.count(), 0)

    def test_analytics_includes_all_featured_items(self):
        analytics = promotion_service.get_promotion_analytics()
        items = [row['item'] for row in analytics]
        self.assertIn(self.cls, items)
        self.assertIn(self.equip, items)

    def test_analytics_includes_ctr(self):
        analytics = promotion_service.get_promotion_analytics()
        for row in analytics:
            self.assertIn('ctr', row)


class PromotionClickViewTests(TestCase):
    """Integration tests for the CR3 click-tracking redirect view."""

    def setUp(self):
        self.user  = make_user()
        self.cat   = make_category('Click')
        self.cls   = make_class('Click Class', category=self.cat, featured=True, days_ahead=2)
        self.equip = make_equipment('Click Machine', category=self.cat, featured=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_class_click_records_event_and_redirects(self):
        url = reverse('gym:featured_click', args=['class', self.cls.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('gym:class_detail', args=[self.cls.pk]))
        self.cls.refresh_from_db()
        self.assertEqual(self.cls.click_count, 1)

    def test_equipment_click_records_event_and_redirects(self):
        url = reverse('gym:featured_click', args=['equipment', self.equip.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('gym:equipment_detail', args=[self.equip.pk]))
        self.equip.refresh_from_db()
        self.assertEqual(self.equip.click_count, 1)

    def test_non_featured_class_click_does_not_record(self):
        non_featured = make_class('Plain', category=self.cat, featured=False, days_ahead=3)
        url = reverse('gym:featured_click', args=['class', non_featured.pk])
        response = self.client.get(url)
        self.assertEqual(PromotionEvent.objects.count(), 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  CR4: Reviews / Ratings
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewModelTests(TestCase):
    """Unit tests for Review model logic."""

    def setUp(self):
        self.user  = make_user()
        self.admin = make_admin()
        self.cat   = make_category('Review')
        self.cls   = make_class('Reviewed Class', category=self.cat, days_ahead=1)
        self.ct    = ContentType.objects.get_for_model(WorkoutClass)

    def _make_review(self, rating=4, comment='Great class'):
        return Review.objects.create(
            content_type=self.ct,
            object_id=self.cls.pk,
            user=self.user,
            rating=rating,
            comment=comment,
        )

    def test_review_defaults_to_pending(self):
        review = self._make_review()
        self.assertEqual(review.status, Review.Status.PENDING)

    def test_approve_transitions_to_approved(self):
        review = self._make_review()
        review.approve(self.admin, note='Looks good')
        self.assertEqual(review.status, Review.Status.APPROVED)
        self.assertEqual(review.moderated_by, self.admin)
        self.assertIsNotNone(review.moderated_at)

    def test_hide_transitions_to_hidden(self):
        review = self._make_review()
        review.hide(self.admin, note='Spam')
        self.assertEqual(review.status, Review.Status.HIDDEN)

    def test_pending_review_is_editable(self):
        review = self._make_review()
        self.assertTrue(review.is_editable)

    def test_approved_review_is_not_editable(self):
        review = self._make_review()
        review.approve(self.admin)
        self.assertFalse(review.is_editable)

    def test_hidden_review_is_not_editable(self):
        review = self._make_review()
        review.hide(self.admin)
        self.assertFalse(review.is_editable)

    def test_stars_display_property(self):
        review = self._make_review(rating=3)
        self.assertEqual(review.stars_display, '★★★☆☆')

    def test_one_review_per_user_per_item_constraint(self):
        """Duplicate review should raise IntegrityError."""
        from django.db import IntegrityError
        self._make_review()
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                content_type=self.ct,
                object_id=self.cls.pk,
                user=self.user,
                rating=2,
                comment='Second attempt',
            )


class ReviewAggregateTests(TestCase):
    """Tests for the class-level aggregate stats."""

    def setUp(self):
        self.admin = make_admin()
        self.cat   = make_category('Agg')
        self.cls   = make_class('Agg Class', category=self.cat, days_ahead=1)
        self.ct    = ContentType.objects.get_for_model(WorkoutClass)

    def _approved_review(self, user, rating):
        r = Review.objects.create(
            content_type=self.ct,
            object_id=self.cls.pk,
            user=user,
            rating=rating,
        )
        r.approve(self.admin)
        return r

    def test_aggregate_counts_only_approved_reviews(self):
        u1 = make_user('u1@t.com')
        u2 = make_user('u2@t.com')
        u3 = make_user('u3@t.com')
        self._approved_review(u1, 5)
        self._approved_review(u2, 3)
        pending = Review.objects.create(
            content_type=self.ct, object_id=self.cls.pk,
            user=u3, rating=1,
        )
        agg = Review.get_aggregate(self.ct, self.cls.pk)
        self.assertEqual(agg['total_count'], 2)  # pending excluded
        self.assertEqual(agg['avg_rating'], 4.0)

    def test_aggregate_avg_rating_precision(self):
        u1 = make_user('r1@t.com')
        u2 = make_user('r2@t.com')
        u3 = make_user('r3@t.com')
        self._approved_review(u1, 5)
        self._approved_review(u2, 4)
        self._approved_review(u3, 3)
        agg = Review.get_aggregate(self.ct, self.cls.pk)
        self.assertEqual(agg['avg_rating'], 4.0)

    def test_aggregate_returns_none_avg_when_no_reviews(self):
        agg = Review.get_aggregate(self.ct, self.cls.pk)
        self.assertIsNone(agg['avg_rating'])
        self.assertEqual(agg['total_count'], 0)

    def test_aggregate_star_breakdown_keys(self):
        u1 = make_user('sb1@t.com')
        self._approved_review(u1, 4)
        agg = Review.get_aggregate(self.ct, self.cls.pk)
        for star in range(1, 6):
            self.assertIn(star, agg['star_breakdown'])


class ReviewSubmissionViewTests(TestCase):
    """Integration tests for the review submission flow."""

    def setUp(self):
        self.member = make_user('reviewer@test.com')
        self.admin  = make_admin()
        self.cat    = make_category('Submit')
        self.cls    = make_class('Submit Class', category=self.cat, days_ahead=1)
        self.ct     = ContentType.objects.get_for_model(WorkoutClass)
        self.client = Client()

    def _make_attended_booking(self):
        return Booking.objects.create(
            user=self.member,
            workout_class=self.cls,
            status=Booking.Status.ATTENDED,
        )

    def test_submit_review_requires_attended_booking(self):
        """Members without an ATTENDED booking must be rejected."""
        self.client.force_login(self.member)
        url = reverse('reviews:submit_review', args=[self.ct.pk, self.cls.pk])
        response = self.client.post(url, {'rating': '4', 'comment': 'Nice'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.count(), 0)

    def test_submit_review_with_attended_booking_creates_pending_review(self):
        self._make_attended_booking()
        self.client.force_login(self.member)
        url = reverse('reviews:submit_review', args=[self.ct.pk, self.cls.pk])
        response = self.client.post(url, {'rating': '5', 'comment': 'Brilliant session'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.status, Review.Status.PENDING)
        self.assertEqual(review.rating, 5)

    def test_duplicate_submission_is_rejected(self):
        self._make_attended_booking()
        self.client.force_login(self.member)
        url = reverse('reviews:submit_review', args=[self.ct.pk, self.cls.pk])
        self.client.post(url, {'rating': '5', 'comment': 'First'})
        response = self.client.post(url, {'rating': '3', 'comment': 'Second'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.count(), 1)  # only the first

    def test_unauthenticated_user_is_redirected_to_login(self):
        url = reverse('reviews:submit_review', args=[self.ct.pk, self.cls.pk])
        response = self.client.post(url, {'rating': '4', 'comment': 'Hi'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response['Location'])


class ModerationViewTests(TestCase):
    """Integration tests for admin moderation workflow."""

    def setUp(self):
        self.member = make_user('mod_member@test.com')
        self.admin  = make_admin('mod_admin@test.com')
        self.cat    = make_category('Mod')
        self.cls    = make_class('Mod Class', category=self.cat, days_ahead=1)
        self.ct     = ContentType.objects.get_for_model(WorkoutClass)
        self.client = Client()

    def _pending_review(self):
        return Review.objects.create(
            content_type=self.ct, object_id=self.cls.pk,
            user=self.member, rating=3, comment='So-so',
        )

    def test_member_cannot_access_moderation_queue(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('reviews:admin_review_list'))
        self.assertEqual(response.status_code, 302)  # redirected by admin_required

    def test_admin_can_view_moderation_queue(self):
        self._pending_review()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('reviews:admin_review_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('reviews', response.context)

    def test_admin_approve_action(self):
        review = self._pending_review()
        self.client.force_login(self.admin)
        url = reverse('reviews:admin_moderate_review', args=[review.pk])
        self.client.post(url, {
            'action': 'approve', 'moderation_note': 'All good',
        })
        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.APPROVED)
        self.assertEqual(review.moderated_by, self.admin)

    def test_admin_hide_action(self):
        review = self._pending_review()
        self.client.force_login(self.admin)
        url = reverse('reviews:admin_moderate_review', args=[review.pk])
        self.client.post(url, {
            'action': 'hide', 'moderation_note': 'Spam content',
        })
        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.HIDDEN)

    def test_moderation_queue_status_tabs_filter_correctly(self):
        r1 = self._pending_review()
        r1.approve(self.admin)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('reviews:admin_review_list') + '?status=APPROVED')
        reviews_in_ctx = list(response.context['reviews'])
        self.assertEqual(len(reviews_in_ctx), 1)

    def test_moderation_note_is_persisted(self):
        review = self._pending_review()
        self.client.force_login(self.admin)
        url = reverse('reviews:admin_moderate_review', args=[review.pk])
        self.client.post(url, {'action': 'approve', 'moderation_note': 'Checked — genuine feedback'})
        review.refresh_from_db()
        self.assertEqual(review.moderation_note, 'Checked — genuine feedback')
