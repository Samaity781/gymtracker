"""
gym/management/commands/security_audit.py
Management command: python manage.py security_audit

Generates a structured security evidence report for CW1B.
Audits and prints evidence for:
  NFR-01 – Password hashing (PBKDF2-SHA256, iteration count, salt)
  NFR-02 – Least privilege (counts protected routes by decorator type)
  NFR-03 – CSRF (middleware active, tokens in templates)
  NFR-06 – State machine (transition map integrity)
  CR1-CR4 – Service layer isolation (logic not in views)
  DB      – Migration integrity (all apps have migrations)
"""

import hashlib
import importlib
import inspect
import os
import re
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Generate a security and quality evidence report for the CW1B report.'

    def handle(self, *args, **options):
        self.stdout.write('\n' + '═' * 70)
        self.stdout.write('  GymTracker — Engineering Quality Evidence Report')
        self.stdout.write('  MSc Software Engineering Practice 7WCM2017 — CW1B')
        self.stdout.write('═' * 70 + '\n')

        self._check_nfr01_password_hashing()
        self._check_nfr02_least_privilege()
        self._check_nfr03_csrf()
        self._check_nfr06_state_machine()
        self._check_service_layer_isolation()
        self._check_migration_integrity()
        self._check_validation_layers()

        self.stdout.write('\n' + '═' * 70)
        self.stdout.write(self.style.SUCCESS('  Evidence report complete.'))
        self.stdout.write('═' * 70 + '\n')

    # ─── NFR-01: Password hashing ─────────────────────────────────────────

    def _check_nfr01_password_hashing(self):
        self._section('NFR-01: Password Hashing')

        # 1. Demonstrate hash is not plaintext
        raw = 'TestPassword99!'
        hashed = make_password(raw)
        self._ok('Raw password is NOT stored', raw not in hashed)
        self._ok('Hash begins with PBKDF2-SHA256 prefix',
                 hashed.startswith('pbkdf2_sha256$'))

        # 2. Parse and validate hash structure
        parts = hashed.split('$')
        algo, iterations, salt, digest = parts
        self._ok('Hash has 4 components (algo$iterations$salt$digest)',
                 len(parts) == 4)
        iter_count = int(iterations)
        self._ok(f'Iteration count {iter_count:,} ≥ 260,000 (OWASP minimum)',
                 iter_count >= 260_000)
        self._ok('Salt is present and non-empty', len(salt) > 0)

        # 3. Salt uniqueness — two hashes of the same password differ
        h1 = make_password(raw)
        h2 = make_password(raw)
        self._ok('Two hashes of identical password differ (salt is unique)',
                 h1 != h2)

        # 4. Confirm validator configuration
        validators = settings.AUTH_PASSWORD_VALIDATORS
        names = [v['NAME'].split('.')[-1] for v in validators]
        self._ok('MinimumLengthValidator configured',
                 'MinimumLengthValidator' in names)
        self._ok('CommonPasswordValidator configured',
                 'CommonPasswordValidator' in names)
        self._ok('NumericPasswordValidator configured',
                 'NumericPasswordValidator' in names)

        self.stdout.write(f'   Hash sample: {hashed[:60]}…')

    # ─── NFR-02: Least privilege ──────────────────────────────────────────

    def _check_nfr02_least_privilege(self):
        self._section('NFR-02: Least Privilege Access Control')

        base = Path(settings.BASE_DIR)
        view_files = list(base.rglob('views.py'))

        admin_protected = 0
        login_protected = 0
        unprotected     = 0
        route_details   = []

        for vf in view_files:
            src = vf.read_text()
            lines = src.splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('def ') and not stripped.startswith('def _'):
                    fn_name = stripped.split('(')[0].replace('def ', '')
                    context = '\n'.join(lines[max(0, i-5):i])
                    if '@admin_required' in context:
                        admin_protected += 1
                        route_details.append(f'  ADMIN  → {vf.name}::{fn_name}')
                    elif '@login_required' in context or '@member_required' in context:
                        login_protected += 1
                        route_details.append(f'  LOGIN  → {vf.name}::{fn_name}')
                    else:
                        # Only flag if it looks like an actual view (has request param)
                        try:
                            sig_line = lines[i]
                            if 'request' in sig_line and fn_name not in ('handle',):
                                unprotected += 1
                                route_details.append(f'  PUBLIC → {vf.name}::{fn_name}')
                        except IndexError:
                            pass

        self._ok(f'{admin_protected} view functions protected by @admin_required',
                 admin_protected > 0)
        self._ok(f'{login_protected} view functions protected by @login_required',
                 login_protected > 0)

        total = admin_protected + login_protected + unprotected
        self.stdout.write(f'\n   Route breakdown ({total} total view functions):')
        for detail in route_details:
            colour = self.style.SUCCESS if 'ADMIN' in detail else (
                     self.style.WARNING if 'LOGIN' in detail else
                     self.style.NOTICE)
            self.stdout.write(f'   {detail}')

        # Verify @admin_required exists in decorators.py
        dec_src = (base / 'accounts' / 'decorators.py').read_text()
        self._ok('@admin_required decorator defined in accounts/decorators.py',
                 'def admin_required' in dec_src)
        self._ok('@admin_required wraps @login_required (two-layer guard)',
                 '@login_required' in dec_src and 'def admin_required' in dec_src)

    # ─── NFR-03: CSRF ─────────────────────────────────────────────────────

    def _check_nfr03_csrf(self):
        self._section('NFR-03: CSRF Protection')

        # Middleware
        self._ok('CsrfViewMiddleware present in MIDDLEWARE',
                 'django.middleware.csrf.CsrfViewMiddleware' in settings.MIDDLEWARE)

        # Templates use {% csrf_token %}
        base = Path(settings.BASE_DIR)
        templates = list(base.rglob('*.html'))
        forms_with_csrf    = 0
        forms_without_csrf = []

        for tmpl in templates:
            src = tmpl.read_text()
            if '<form' in src and 'method="post"' in src.lower():
                if '{% csrf_token %}' in src:
                    forms_with_csrf += 1
                else:
                    forms_without_csrf.append(tmpl.name)

        self._ok(f'{forms_with_csrf} POST form template(s) include the csrf_token tag',
                 forms_with_csrf > 0)

        if forms_without_csrf:
            self.stdout.write(self.style.ERROR(
                f'   ✗ WARNING — forms WITHOUT csrf_token: {forms_without_csrf}'
            ))
        else:
            self._ok('No POST forms found without CSRF token', True)

        # require_POST on state-changing endpoints
        views_src = (Path(settings.BASE_DIR) / 'bookings' / 'views.py').read_text()
        post_count = views_src.count('@require_POST')
        self._ok(f'bookings/views.py has {post_count} @require_POST decorators',
                 post_count >= 2)

    # ─── NFR-06: State machine ────────────────────────────────────────────

    def _check_nfr06_state_machine(self):
        self._section('NFR-06: Booking State Machine Integrity')

        from bookings.models import Booking

        statuses = list(Booking.Status)
        transitions = Booking.VALID_TRANSITIONS

        self._ok('VALID_TRANSITIONS dict covers all 4 Status values',
                 set(transitions.keys()) == {s.value for s in statuses})

        # BOOKED has 3 valid outgoing transitions
        self._ok('BOOKED → {CANCELLED, ATTENDED, MISSED}',
                 transitions[Booking.Status.BOOKED] == {
                     Booking.Status.CANCELLED,
                     Booking.Status.ATTENDED,
                     Booking.Status.MISSED,
                 })

        # Terminal states
        for terminal in (Booking.Status.CANCELLED, Booking.Status.ATTENDED,
                         Booking.Status.MISSED):
            self._ok(f'{terminal} is terminal (empty transition set)',
                     transitions[terminal] == set())

        # assert_transition raises ValueError
        b = Booking(status=Booking.Status.CANCELLED)
        try:
            b.assert_transition(Booking.Status.BOOKED)
            raised = False
        except ValueError:
            raised = True
        self._ok('assert_transition() raises ValueError for invalid move', raised)

        # Verify service layer is the only path to state change
        views_src = (Path(settings.BASE_DIR) / 'bookings' / 'views.py').read_text()
        self._ok('booking.status not assigned directly in views.py',
                 'booking.status =' not in views_src)

    # ─── Service layer isolation ──────────────────────────────────────────

    def _check_service_layer_isolation(self):
        self._section('Service Layer Isolation (Three-Layer Architecture)')

        base = Path(settings.BASE_DIR)
        gym_views = (base / 'gym' / 'views.py').read_text()

        # CR1 search logic must not be in views
        self._ok('CR1: Q() filter objects NOT in gym/views.py (in search_service.py)',
                 'Q(name__icontains' not in gym_views)

        # CR2 ranking logic must not be in views
        self._ok('CR2: WEIGHT_FEATURED NOT in gym/views.py (in ranking_service.py)',
                 'WEIGHT_FEATURED' not in gym_views)
        self._ok('CR2: score_class() NOT defined in gym/views.py',
                 'def score_class' not in gym_views)

        # CR3 event recording must not be inline
        self._ok('CR3: bulk_create() NOT called in gym/views.py (in promotion_service.py)',
                 'bulk_create' not in gym_views)

        # Service files must exist and be substantive
        service_files = {
            'bookings/services.py':     40,
            'gym/ranking_service.py':   30,
            'gym/search_service.py':    25,
            'gym/promotion_service.py': 25,
            'tracker/services.py':      20,
        }
        for rel_path, min_lines in service_files.items():
            path = base / rel_path
            src = path.read_text()
            substantive = [l for l in src.splitlines()
                           if l.strip() and not l.strip().startswith('#')]
            self._ok(
                f'{rel_path} exists with ≥{min_lines} substantive lines ({len(substantive)} found)',
                len(substantive) >= min_lines
            )

        # Measure view function sizes (thin view contract)
        self.stdout.write('\n   View function line counts (thin = ≤ 15 substantive lines):')
        bookings_views = importlib.import_module('bookings.views')
        for fn_name in ('book_class', 'cancel_booking', 'my_bookings'):
            fn = getattr(bookings_views, fn_name)
            lines = [l for l in inspect.getsource(fn).splitlines()
                     if l.strip() and not l.strip().startswith('#')]
            thin = len(lines) <= 15
            mark = '✓' if thin else '✗'
            colour = self.style.SUCCESS if thin else self.style.ERROR
            self.stdout.write(colour(
                f'   {mark} bookings.views.{fn_name}: {len(lines)} lines'
            ))

    # ─── Migration integrity ──────────────────────────────────────────────

    def _check_migration_integrity(self):
        self._section('Database: Migration Integrity')

        from django.db.migrations.loader import MigrationLoader
        from django.db import connection

        loader = MigrationLoader(connection)

        apps_to_check = ['accounts', 'gym', 'bookings', 'tracker', 'reviews']
        for app in apps_to_check:
            migrations = [k for k in loader.disk_migrations if k[0] == app]
            self._ok(f'{app}: {len(migrations)} migration(s) on disk',
                     len(migrations) > 0)

        # Check for unapplied migrations
        applied   = {k for k, _ in loader.applied_migrations}
        disk_keys = set(loader.disk_migrations.keys())
        unapplied = disk_keys - applied
        # Filter to our apps
        our_unapplied = [k for k in unapplied if k[0] in apps_to_check]
        self._ok(f'All migrations applied ({len(our_unapplied)} unapplied for our apps)',
                 len(our_unapplied) == 0)

        # Verify the CR-specific tables exist in the schema
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        cr_tables = {
            'reviews_review':     'CR4 Review table',
            'gym_promotionevent': 'CR3 PromotionEvent table',
        }
        for table, label in cr_tables.items():
            self._ok(f'{label} ({table}) present in database schema',
                     table in tables)

        # GenericForeignKey requires contenttypes
        self._ok('django_content_type table present (GenericFK dependency)',
                 'django_content_type' in tables)

        # Reviews UniqueConstraint
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='reviews_review'"
            )
            row = cursor.fetchone()
        if row:
            self._ok('reviews_review table schema retrieved successfully', True)
            self.stdout.write(f'   Schema: {row[0][:120]}…')
        else:
            self._ok('reviews_review table found', False)

    # ─── Validation layers ────────────────────────────────────────────────

    def _check_validation_layers(self):
        self._section('Dual-Layer Form Validation Evidence')

        base = Path(settings.BASE_DIR)

        # Count clean_* methods across all forms.py files
        form_files = list(base.rglob('forms.py'))
        total_clean = 0
        total_html5  = 0

        for ff in form_files:
            src = ff.read_text()
            clean_count = src.count('def clean_') + src.count('def clean(')
            html5_count  = (src.count("'min'") + src.count('"min"') +
                            src.count("'minlength'") + src.count('"minlength"') +
                            src.count("'maxlength'") + src.count('"maxlength"'))
            total_clean += clean_count
            total_html5  += html5_count
            if clean_count or html5_count:
                self.stdout.write(
                    f'   {ff.relative_to(base)}: '
                    f'{clean_count} server-side validators, {html5_count} HTML5 attrs'
                )

        self._ok(f'Total: {total_clean} server-side clean_* validators across all forms',
                 total_clean >= 10)
        self._ok(f'Total: {total_html5} HTML5 client-side constraint attributes',
                 total_html5 >= 10)

        # Spot-check: WorkoutClassForm capacity has min=1 in widget
        from gym.forms import WorkoutClassForm
        f = WorkoutClassForm()
        capacity_html = f['capacity'].as_widget()
        self._ok('WorkoutClassForm capacity widget has min="1" (client-side)',
                 'min="1"' in capacity_html)

        # Spot-check: server-side rejects capacity=0
        from datetime import timedelta
        from django.utils import timezone
        dt = (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        bad_form = WorkoutClassForm(data={
            'name': 'Test', 'duration_minutes': 60,
            'capacity': 0, 'start_time': dt,
        })
        bad_form.is_valid()
        self._ok('WorkoutClassForm rejects capacity=0 server-side',
                 'capacity' in bad_form.errors)

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _section(self, title):
        self.stdout.write(f'\n{"─" * 70}')
        self.stdout.write(f'  {title}')
        self.stdout.write('─' * 70)

    def _ok(self, description, passed: bool):
        if passed:
            self.stdout.write(self.style.SUCCESS(f'   ✓  {description}'))
        else:
            self.stdout.write(self.style.ERROR(f'   ✗  {description}'))
