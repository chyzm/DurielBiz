from django.urls import path

from .views import (
    checkout_preview,
    customer_detail,
    customer_list,
    customer_lookup_api,
    customer_update,
    pos_terminal,
    receipt_detail,
    receipt_search,
    sales_history,
    sales_history_export_csv,
    void_sale_view,
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
    path("pos/checkout-preview/", checkout_preview, name="checkout-preview"),
    path("receipts/search/", receipt_search, name="receipt-search"),
    path("receipt/<int:pk>/", receipt_detail, name="receipt"),
    path("receipt/<int:pk>/void/", void_sale_view, name="void"),
]
