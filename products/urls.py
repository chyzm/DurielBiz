from django.urls import path

from .views import (
    category_create,
    category_delete,
    category_detail,
    category_list,
    category_update,
    product_create,
    product_delete,
    product_detail,
    product_list,
    product_update,
)

app_name = "products"

urlpatterns = [
    path("", product_list, name="list"),
    path("new/", product_create, name="create"),
    path("categories/", category_list, name="category-list"),
    path("categories/new/", category_create, name="category-create"),
    path("categories/<int:pk>/", category_detail, name="category-detail"),
    path("categories/<int:pk>/edit/", category_update, name="category-update"),
    path("categories/<int:pk>/delete/", category_delete, name="category-delete"),
    path("<int:pk>/", product_detail, name="detail"),
    path("<int:pk>/edit/", product_update, name="update"),
    path("<int:pk>/delete/", product_delete, name="delete"),
]
