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
    admin_reset_password,
    create_cloud_business,
    password_change_local,
    role_home,
    service_admin_dashboard,
    activate_tools_subscription,
    user_delete,
    user_detail,
    user_management,
    user_update,
)

app_name = "accounts"

urlpatterns = [
    path("home/", role_home, name="home"),
    path("login/", AccountLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password-reset/", CloudPasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", CloudPasswordResetDoneView.as_view(), name="password-reset-done"),
    path("reset/verify/", CloudPasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("reset/done/", CloudPasswordResetCompleteView.as_view(), name="password-reset-complete"),
    path("password-change/", CloudPasswordChangeView.as_view(), name="password-change"),
    path("password-change/done/", CloudPasswordChangeDoneView.as_view(), name="password-change-done"),
    path("password-change/local/", password_change_local, name="password-change-local"),
    path("password-change/required/", password_change_local, name="password-change-required"),
    path("about-support/", about_support, name="about-support"),
    path("admin-center/", admin_center, name="admin-center"),
    path("service-admin/", service_admin_dashboard, name="service-admin"),
    path("service-admin/tools/<int:pk>/activate/", activate_tools_subscription, name="tools-subscription-activate"),
    path("service-admin/cloud/create/", create_cloud_business, name="service-admin-create-cloud-business"),
    path("activity-log/", activity_log_list, name="activity-log"),
    path("users/", user_management, name="user-management"),
    path("users/<int:pk>/", user_detail, name="user-detail"),
    path("users/<int:pk>/edit/", user_update, name="user-update"),
    path("users/<int:pk>/reset-password/", admin_reset_password, name="user-reset-password"),
    path("users/<int:pk>/delete/", user_delete, name="user-delete"),
]
