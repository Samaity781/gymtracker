"""GymTracker – root URL configuration."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirect bare root to dashboard (or login if not authenticated)
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),

    # App URL namespaces
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('dashboard/', include('gym.urls', namespace='gym')),
    path('bookings/', include('bookings.urls', namespace='bookings')),
    path('tracker/', include('tracker.urls', namespace='tracker')),
    path('reviews/', include('reviews.urls', namespace='reviews')),

    # Django built-in password reset (uses console email in dev)
    path('accounts/', include('django.contrib.auth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
