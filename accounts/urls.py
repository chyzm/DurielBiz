from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from .forms import StyledPasswordChangeForm, StyledPasswordResetForm, StyledSetPasswordForm
from .views import about_support, activity_log_list, admin_center, role_home, user_delete, user_detail, user_management, user_update
from cloudsync.views import signup as cloud_signup

app_name = "accounts"

urlpatterns = [
    path("home/", role_home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("signup/", cloud_signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=StyledPasswordResetForm,
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password-reset-done"),
        ),
        name="password-reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password-reset-done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=StyledSetPasswordForm,
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password-reset-complete"),
        ),
        name="password-reset-confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password-reset-complete",
    ),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            form_class=StyledPasswordChangeForm,
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("accounts:password-change-done"),
        ),
        name="password-change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
        name="password-change-done",
    ),
    path("about-support/", about_support, name="about-support"),
    path("admin-center/", admin_center, name="admin-center"),
    path("activity-log/", activity_log_list, name="activity-log"),
    path("users/", user_management, name="user-management"),
    path("users/<int:pk>/", user_detail, name="user-detail"),
    path("users/<int:pk>/edit/", user_update, name="user-update"),
    path("users/<int:pk>/delete/", user_delete, name="user-delete"),
]
