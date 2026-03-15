from django.contrib.auth import views as auth_views
from django.urls import path

from .views import about_support, activity_log_list, admin_center, role_home, user_delete, user_detail, user_management, user_update
from cloudsync.views import signup as cloud_signup

app_name = "accounts"

urlpatterns = [
    path("home/", role_home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("signup/", cloud_signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("about-support/", about_support, name="about-support"),
    path("admin-center/", admin_center, name="admin-center"),
    path("activity-log/", activity_log_list, name="activity-log"),
    path("users/", user_management, name="user-management"),
    path("users/<int:pk>/", user_detail, name="user-detail"),
    path("users/<int:pk>/edit/", user_update, name="user-update"),
    path("users/<int:pk>/delete/", user_delete, name="user-delete"),
]
