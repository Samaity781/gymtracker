from django.urls import path
from . import views

app_name = 'gym'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # CR3: click tracking redirect — preserves featured click signal before detail page
    path('featured/<str:item_type>/<int:pk>/click/', views.featured_click, name='featured_click'),

    # Workout Classes (member)
    path('classes/', views.class_list, name='class_list'),
    path('classes/<int:pk>/', views.class_detail, name='class_detail'),

    # Equipment (member)
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/<int:pk>/', views.equipment_detail, name='equipment_detail'),

    # Admin: Classes
    path('manage/classes/', views.admin_class_list, name='admin_class_list'),
    path('manage/classes/create/', views.admin_class_create, name='admin_class_create'),
    path('manage/classes/<int:pk>/edit/', views.admin_class_edit, name='admin_class_edit'),
    path('manage/classes/<int:pk>/toggle/', views.admin_class_toggle_active, name='admin_class_toggle'),
    path('manage/classes/<int:pk>/delete/', views.admin_class_delete, name='admin_class_delete'),

    # Admin: Equipment
    path('manage/equipment/', views.admin_equipment_list, name='admin_equipment_list'),
    path('manage/equipment/create/', views.admin_equipment_create, name='admin_equipment_create'),
    path('manage/equipment/<int:pk>/edit/', views.admin_equipment_edit, name='admin_equipment_edit'),
    path('manage/equipment/<int:pk>/toggle/', views.admin_equipment_toggle_active, name='admin_equipment_toggle'),
    path('manage/equipment/<int:pk>/delete/', views.admin_equipment_delete, name='admin_equipment_delete'),

    # Admin: Categories
    path('manage/categories/', views.admin_category_list, name='admin_category_list'),
    path('manage/categories/create/', views.admin_category_create, name='admin_category_create'),
    path('manage/categories/<int:pk>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('manage/categories/<int:pk>/delete/', views.admin_category_delete, name='admin_category_delete'),

    # Admin: CR3 promotions analytics
    path('manage/promotions/', views.admin_promotions, name='admin_promotions'),
]
