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
    business_setup,
    activity_log_list,
    admin_center,
    admin_reset_password,
    password_change_local,
    role_home,
    superadmin_dashboard,
    superadmin_business_action,
    superadmin_business_activity,
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
    path("businesses/setup/", business_setup, name="business-setup"),
    path("superadmin/", superadmin_dashboard, name="superadmin-dashboard"),
    path("superadmin/businesses/<int:pk>/action/", superadmin_business_action, name="superadmin-business-action"),
    path("superadmin/businesses/<int:pk>/activity/", superadmin_business_activity, name="superadmin-business-activity"),
    path("activity-log/", activity_log_list, name="activity-log"),
    path("users/", user_management, name="user-management"),
    path("users/<signed_int:pk>/", user_detail, name="user-detail"),
    path("users/<signed_int:pk>/edit/", user_update, name="user-update"),
    path("users/<signed_int:pk>/reset-password/", admin_reset_password, name="user-reset-password"),
    path("users/<signed_int:pk>/delete/", user_delete, name="user-delete"),
]
