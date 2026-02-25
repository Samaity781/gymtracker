from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('my/', views.my_bookings, name='my_bookings'),
    path('class/<int:pk>/book/', views.book_class, name='book_class'),
    path('<int:pk>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('equipment/<int:pk>/book/', views.book_equipment_view, name='book_equipment'),

    # Admin
    path('admin/', views.admin_booking_list, name='admin_booking_list'),
    path('admin/<int:pk>/mark/', views.admin_mark_booking, name='admin_mark_booking'),
]
