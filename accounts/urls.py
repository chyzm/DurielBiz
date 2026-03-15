from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    AccountLoginView,
    CloudPasswordChangeDoneView,
    CloudPasswordChangeView,
    CloudPasswordResetCompleteView,
    CloudPasswordResetConfirmView,
    CloudPasswordResetDoneView,
    CloudPasswordResetView,
    about_support,
    activity_log_list,
    admin_center,
    role_home,
    user_delete,
    user_detail,
    user_management,
    user_update,
)
from cloudsync.views import signup as cloud_signup

app_name = "accounts"

urlpatterns = [
    path("home/", role_home, name="home"),
    path("login/", AccountLoginView.as_view(), name="login"),
    path("signup/", cloud_signup, name="signup"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password-reset/", CloudPasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", CloudPasswordResetDoneView.as_view(), name="password-reset-done"),
    path("reset/<uidb64>/<token>/", CloudPasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("reset/done/", CloudPasswordResetCompleteView.as_view(), name="password-reset-complete"),
    path("password-change/", CloudPasswordChangeView.as_view(), name="password-change"),
    path("password-change/done/", CloudPasswordChangeDoneView.as_view(), name="password-change-done"),
    path("about-support/", about_support, name="about-support"),
    path("admin-center/", admin_center, name="admin-center"),
    path("activity-log/", activity_log_list, name="activity-log"),
    path("users/", user_management, name="user-management"),
    path("users/<int:pk>/", user_detail, name="user-detail"),
    path("users/<int:pk>/edit/", user_update, name="user-update"),
    path("users/<int:pk>/delete/", user_delete, name="user-delete"),
]
