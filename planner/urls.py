from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),

    # Student tasks
    path('tasks/add/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/edit/', views.task_update, name='task_update'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/topic/', views.task_topic, name='task_topic'),

    # Admin
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/holidays/', views.holiday_list, name='holiday_list'),
    path('admin-dashboard/holidays/add/', views.holiday_create, name='holiday_create'),
    path('admin-dashboard/holidays/<int:pk>/edit/', views.holiday_update, name='holiday_update'),
    path('admin-dashboard/holidays/<int:pk>/delete/', views.holiday_delete, name='holiday_delete'),
    path('admin-dashboard/records/', views.manage_records, name='manage_records'),
    path('admin-dashboard/records/users/<int:pk>/role/', views.user_toggle_role, name='user_toggle_role'),
    path('admin-dashboard/records/users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('admin-dashboard/records/tasks/<int:pk>/delete/', views.record_task_delete, name='record_task_delete'),
]