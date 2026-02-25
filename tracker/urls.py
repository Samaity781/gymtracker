from django.urls import path
from . import views

app_name = 'tracker'

urlpatterns = [
    # Sessions
    path('', views.session_list, name='session_list'),
    path('sessions/log/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/', views.session_detail, name='session_detail'),
    path('sessions/<int:pk>/edit/', views.session_edit, name='session_edit'),
    path('sessions/<int:pk>/delete/', views.session_delete, name='session_delete'),

    # Sets (within an entry)
    path('entries/<int:entry_pk>/sets/', views.entry_sets, name='entry_sets'),

    # Progress
    path('progress/', views.progress_view, name='progress'),

    # Routines
    path('routines/', views.routine_list, name='routine_list'),
    path('routines/create/', views.routine_create, name='routine_create'),
    path('routines/<int:pk>/edit/', views.routine_edit, name='routine_edit'),
    path('routines/<int:pk>/delete/', views.routine_delete, name='routine_delete'),
]
