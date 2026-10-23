from django.contrib import admin
from django.urls import include, path

from planner import views as planner_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/logout/', planner_views.logout_view, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('planner.urls')),
]