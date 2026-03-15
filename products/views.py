from django.contrib import messages
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import get_user_branch, role_required
from inventory.models import InventoryLog
from inventory.services import apply_inventory_adjustment
from pos_system.pagination import paginate_queryset
from reports.models import Branch, BusinessSettings

from .forms import CategoryForm, ProductForm
from .models import Category, Product
from .stock import get_branch_stock, product_queryset_for_branch


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def product_list(request):
    search = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    threshold = timezone.localdate() + timedelta(days=56)
    user_branch = get_user_branch(request.user)

    products = product_queryset_for_branch(
        user_branch,
        Product.objects.select_related("category", "supplier"),
    ).order_by("name")
    if user_branch is not None:
        products = products.filter(branch_stocks__branch=user_branch).distinct()
    if search:
        products = products.filter(Q(name__icontains=search) | Q(barcode__icontains=search))
    if category_slug:
        products = products.filter(category__slug=category_slug)
    products_page = paginate_queryset(request, products, per_page=15)

    if user_branch is not None:
        categories = (
            Category.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True)
            )
            .filter(product_count__gt=0)
            .order_by("name")
        )
        all_products = product_queryset_for_branch(
            user_branch,
            Product.objects.filter(branch_stocks__branch=user_branch).distinct(),
        )
    else:
        categories = Category.objects.annotate(product_count=Count("products")).order_by("name")
        all_products = Product.objects.all()

    context = {
        "products": products_page,
        "categories": categories,
        "search": search,
        "selected_category": category_slug,
        "total_products": all_products.count(),
        "active_products": all_products.filter(is_active=True).count(),
        "low_stock_count": (
            all_products.filter(is_active=True, branch_quantity__lte=F("reorder_level")).count()
            if user_branch is not None
            else all_products.filter(is_active=True, quantity__lte=F("reorder_level")).count()
        ),
        "expiring_count": all_products.filter(
            is_active=True, expiry_date__isnull=False, expiry_date__lte=threshold
        ).count(),
    }
    return render(request, "products/product_list.html", context)


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def product_create(request):
    form = ProductForm(request.POST or None, include_opening_fields=True, user=request.user)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        opening_stock = form.cleaned_data.get("opening_stock") or 0
        opening_branch = get_user_branch(request.user) or form.cleaned_data.get("opening_branch") or BusinessSettings.get_solo().default_branch
        if opening_branch:
            get_branch_stock(product, opening_branch)
        if opening_stock:
            apply_inventory_adjustment(
                branch=opening_branch,
                product=product,
                action=InventoryLog.Action.ADD,
                quantity=opening_stock,
                reason="Opening stock on product creation",
                reference=f"product-opening:{product.pk}",
                actor=request.user,
            )
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PRODUCTS,
            action="product_created",
            description=f"{request.user.username} created product {product.name}",
            entity_type="product",
            entity_id=product.pk,
        )
        if opening_stock:
            messages.success(request, f"{product.name} added successfully with opening stock of {opening_stock}.")
        else:
            messages.success(request, f"{product.name} added successfully.")
        return redirect("products:list")
    return render(request, "products/product_form.html", {"form": form})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def product_detail(request, pk):
    user_branch = get_user_branch(request.user)
    product_queryset = Product.objects.select_related("category", "supplier")
    if user_branch is not None:
        product_queryset = product_queryset.filter(branch_stocks__branch=user_branch).distinct()
    product = get_object_or_404(product_queryset, pk=pk)
    branch_stocks = product.branch_stocks.select_related("branch").order_by("branch__name")
    if user_branch is not None:
        branch_stocks = branch_stocks.filter(branch=user_branch)
    return render(
        request,
        "products/product_detail.html",
        {"product": product, "branch_stocks": branch_stocks, "branch_count": branch_stocks.count()},
    )


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def product_update(request, pk):
    user_branch = get_user_branch(request.user)
    product_queryset = Product.objects.all()
    if user_branch is not None:
        product_queryset = product_queryset.filter(branch_stocks__branch=user_branch).distinct()
    product = get_object_or_404(product_queryset, pk=pk)
    form = ProductForm(
        request.POST or None,
        instance=product,
        include_opening_fields=False,
        include_branch_field=True,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        selected_branch = get_user_branch(request.user) or form.cleaned_data.get("opening_branch")
        if selected_branch:
            get_branch_stock(product, selected_branch)
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PRODUCTS,
            action="product_updated",
            description=f"{request.user.username} updated product {product.name}",
            entity_type="product",
            entity_id=product.pk,
        )
        if selected_branch:
            messages.success(request, f"{product.name} updated successfully for {selected_branch.name}.")
        else:
            messages.success(request, f"{product.name} updated successfully.")
        return redirect("products:detail", pk=product.pk)
    return render(request, "products/product_form.html", {"form": form, "product": product})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def product_delete(request, pk):
    user_branch = get_user_branch(request.user)
    product_queryset = Product.objects.all()
    if user_branch is not None:
        product_queryset = product_queryset.filter(branch_stocks__branch=user_branch).distinct()
    product = get_object_or_404(product_queryset, pk=pk)
    if request.method == "POST":
        product_name = product.name
        try:
            product.delete()
            log_activity(
                user=request.user,
                module=ActivityLog.Module.PRODUCTS,
                action="product_deleted",
                description=f"{request.user.username} deleted product {product_name}",
                entity_type="product",
                entity_id=pk,
            )
            messages.success(request, f"{product_name} deleted successfully.")
        except ProtectedError:
            product.is_active = False
            product.save(update_fields=["is_active", "updated_at"])
            log_activity(
                user=request.user,
                module=ActivityLog.Module.PRODUCTS,
                action="product_deactivated",
                description=f"{request.user.username} deactivated product {product_name}",
                entity_type="product",
                entity_id=product.pk,
            )
            messages.warning(request, f"{product_name} has related records and was deactivated instead.")
        return redirect("products:list")
    return render(request, "products/product_confirm_delete.html", {"product": product})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def category_list(request):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        categories = (
            Category.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True)
            )
            .filter(product_count__gt=0)
            .order_by("name")
        )
    else:
        categories = Category.objects.annotate(product_count=Count("products")).order_by("name")
    return render(
        request,
        "products/category_list.html",
        {"categories": paginate_queryset(request, categories, per_page=12)},
    )


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PRODUCTS,
            action="category_created",
            description=f"{request.user.username} created category {category.name}",
            entity_type="category",
            entity_id=category.pk,
        )
        messages.success(request, f"{category.name} added successfully.")
        return redirect("products:category-list")
    return render(request, "products/category_form.html", {"form": form})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def category_detail(request, pk):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        category = get_object_or_404(
            Category.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True)
            ).filter(product_count__gt=0),
            pk=pk,
        )
        category_products = product_queryset_for_branch(
            user_branch,
            category.products.filter(branch_stocks__branch=user_branch).distinct(),
        ).order_by("name")
    else:
        category = get_object_or_404(Category.objects.annotate(product_count=Count("products")), pk=pk)
        category_products = category.products.order_by("name")
    products = paginate_queryset(request, category_products, per_page=10, page_param="products_page")
    return render(request, "products/category_detail.html", {"category": category, "products": products})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def category_update(request, pk):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        category = get_object_or_404(
            Category.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True)
            ).filter(product_count__gt=0),
            pk=pk,
        )
    else:
        category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PRODUCTS,
            action="category_updated",
            description=f"{request.user.username} updated category {category.name}",
            entity_type="category",
            entity_id=category.pk,
        )
        messages.success(request, f"{category.name} updated successfully.")
        return redirect("products:category-detail", pk=category.pk)
    return render(request, "products/category_form.html", {"form": form, "category": category})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def category_delete(request, pk):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        category = get_object_or_404(
            Category.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True)
            ).filter(product_count__gt=0),
            pk=pk,
        )
    else:
        category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category_name = category.name
        try:
            category.delete()
            log_activity(
                user=request.user,
                module=ActivityLog.Module.PRODUCTS,
                action="category_deleted",
                description=f"{request.user.username} deleted category {category_name}",
                entity_type="category",
                entity_id=pk,
            )
            messages.success(request, f"{category_name} deleted successfully.")
        except ProtectedError:
            messages.error(request, f"{category_name} is in use by products and cannot be deleted.")
            return redirect("products:category-detail", pk=pk)
        return redirect("products:category-list")
    return render(request, "products/category_confirm_delete.html", {"category": category})
