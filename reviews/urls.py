from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    # Member: submit and edit
    path('submit/<int:content_type_id>/<int:object_id>/', views.submit_review, name='submit_review'),
    path('<int:pk>/edit/', views.edit_review, name='edit_review'),

    # Admin: moderation queue
    path('manage/', views.admin_review_list, name='admin_review_list'),
    path('manage/<int:pk>/', views.admin_moderate_review, name='admin_moderate_review'),
]
