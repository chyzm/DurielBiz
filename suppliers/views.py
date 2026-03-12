from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import get_user_branch, role_required
from pos_system.pagination import paginate_queryset

from .forms import SupplierForm
from .models import Supplier


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def supplier_list(request):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        suppliers = (
            Supplier.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True),
                purchase_count=Count("purchases", filter=Q(purchases__branch=user_branch), distinct=True),
            )
            .filter(Q(product_count__gt=0) | Q(purchase_count__gt=0))
            .order_by("name")
        )
    else:
        suppliers = Supplier.objects.annotate(product_count=Count("products"), purchase_count=Count("purchases")).order_by("name")
    return render(
        request,
        "suppliers/supplier_list.html",
        {"suppliers": paginate_queryset(request, suppliers, per_page=12)},
    )


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PRODUCTS,
            action="supplier_created",
            description=f"{request.user.username} created supplier {supplier.name}",
            entity_type="supplier",
            entity_id=supplier.pk,
        )
        messages.success(request, f"{supplier.name} added successfully.")
        return redirect("suppliers:list")
    return render(request, "suppliers/supplier_form.html", {"form": form})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def supplier_detail(request, pk):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        supplier = get_object_or_404(
            Supplier.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True),
                purchase_count=Count("purchases", filter=Q(purchases__branch=user_branch), distinct=True),
            ).filter(Q(product_count__gt=0) | Q(purchase_count__gt=0)),
            pk=pk,
        )
        supplier_products = supplier.products.filter(branch_stocks__branch=user_branch).order_by("name").distinct()
        supplier_purchases = supplier.purchases.filter(branch=user_branch).order_by("-received_at")
    else:
        supplier = get_object_or_404(
            Supplier.objects.annotate(product_count=Count("products"), purchase_count=Count("purchases")),
            pk=pk,
        )
        supplier_products = supplier.products.order_by("name")
        supplier_purchases = supplier.purchases.order_by("-received_at")
    products = paginate_queryset(request, supplier_products, per_page=8, page_param="products_page")
    purchases = paginate_queryset(
        request,
        supplier_purchases,
        per_page=8,
        page_param="purchases_page",
    )
    return render(
        request,
        "suppliers/supplier_detail.html",
        {"supplier": supplier, "products": products, "purchases": purchases},
    )


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def supplier_update(request, pk):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        supplier = get_object_or_404(
            Supplier.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True),
                purchase_count=Count("purchases", filter=Q(purchases__branch=user_branch), distinct=True),
            ).filter(Q(product_count__gt=0) | Q(purchase_count__gt=0)),
            pk=pk,
        )
    else:
        supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.PRODUCTS,
            action="supplier_updated",
            description=f"{request.user.username} updated supplier {supplier.name}",
            entity_type="supplier",
            entity_id=supplier.pk,
        )
        messages.success(request, f"{supplier.name} updated successfully.")
        return redirect("suppliers:detail", pk=supplier.pk)
    return render(request, "suppliers/supplier_form.html", {"form": form, "supplier": supplier})


@login_required
@role_required(User.Role.ADMIN, User.Role.INVENTORY)
def supplier_delete(request, pk):
    user_branch = get_user_branch(request.user)
    if user_branch is not None:
        supplier = get_object_or_404(
            Supplier.objects.annotate(
                product_count=Count("products", filter=Q(products__branch_stocks__branch=user_branch), distinct=True),
                purchase_count=Count("purchases", filter=Q(purchases__branch=user_branch), distinct=True),
            ).filter(Q(product_count__gt=0) | Q(purchase_count__gt=0)),
            pk=pk,
        )
    else:
        supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        supplier_name = supplier.name
        try:
            supplier.delete()
            log_activity(
                user=request.user,
                module=ActivityLog.Module.PRODUCTS,
                action="supplier_deleted",
                description=f"{request.user.username} deleted supplier {supplier_name}",
                entity_type="supplier",
                entity_id=pk,
            )
            messages.success(request, f"{supplier_name} deleted successfully.")
        except ProtectedError:
            messages.error(request, f"{supplier_name} is linked to purchases and cannot be deleted.")
            return redirect("suppliers:detail", pk=pk)
        return redirect("suppliers:list")
    return render(request, "suppliers/supplier_confirm_delete.html", {"supplier": supplier})
