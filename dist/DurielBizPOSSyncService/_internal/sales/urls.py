from django.urls import path

from .views import (
    customer_detail,
    customer_list,
    customer_lookup_api,
    customer_update,
    pos_terminal,
    receipt_detail,
    sales_history,
    sales_history_export_csv,
)

app_name = "sales"

urlpatterns = [
    path("customers/", customer_list, name="customer-list"),
    path("customers/lookup/", customer_lookup_api, name="customer-lookup"),
    path("customers/<int:pk>/", customer_detail, name="customer-detail"),
    path("customers/<int:pk>/edit/", customer_update, name="customer-update"),
    path("history/", sales_history, name="history"),
    path("history/export/", sales_history_export_csv, name="history-export"),
    path("pos/", pos_terminal, name="pos"),
    path("receipt/<int:pk>/", receipt_detail, name="receipt"),
]
