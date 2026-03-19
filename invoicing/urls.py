from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    ToolsLoginView,
    ToolsPasswordChangeView,
    ToolsPasswordResetCompleteView,
    ToolsPasswordResetConfirmView,
    ToolsPasswordResetDoneView,
    ToolsPasswordResetView,
    ToolsSignupView,
    business_settings,
    dashboard,
    document_create,
    document_detail,
    document_list,
    document_pdf,
    document_update,
    service_create,
    service_delete,
    service_list,
    service_update,
    tools_home,
)

app_name = "invoicing"

urlpatterns = [
    path("", tools_home, name="home"),
    path("signup/", ToolsSignupView.as_view(), name="signup"),
    path("login/", ToolsLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="invoicing:home"), name="logout"),
    path("password-reset/", ToolsPasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", ToolsPasswordResetDoneView.as_view(), name="password-reset-done"),
    path("reset/<uidb64>/<token>/", ToolsPasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("reset/done/", ToolsPasswordResetCompleteView.as_view(), name="password-reset-complete"),
    path("password-change/", ToolsPasswordChangeView.as_view(), name="password-change"),
    path("dashboard/", dashboard, name="dashboard"),
    path("business/", business_settings, name="business-settings"),
    path("services/", service_list, name="service-list"),
    path("services/new/", service_create, name="service-create"),
    path("services/<int:pk>/edit/", service_update, name="service-update"),
    path("services/<int:pk>/delete/", service_delete, name="service-delete"),
    path("invoice/", document_list, name="document-list"),
    path("invoice/new/<str:document_type>/", document_create, name="document-create"),
    path("invoice/<int:pk>/", document_detail, name="document-detail"),
    path("invoice/<int:pk>/edit/", document_update, name="document-update"),
    path("invoice/<int:pk>/pdf/", document_pdf, name="document-pdf"),
]
