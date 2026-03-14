from django.db.models import F, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from .models import BranchStock, Product


def get_branch_stock(product, branch):
    if branch is None:
        return None

    stock = BranchStock.objects.select_for_update().filter(product=product, branch=branch).first()
    if stock is None:
        stock = BranchStock.objects.create(product=product, branch=branch, quantity=0)
    return stock


def branch_quantity(product, branch):
    if branch is None:
        return product.quantity

    prefetched = getattr(product, "selected_branch_stocks", None)
    if prefetched is not None:
        return prefetched[0].quantity if prefetched else 0

    stock = product.branch_stocks.filter(branch=branch).only("quantity").first()
    return stock.quantity if stock else 0


def apply_global_delta(product, delta):
    if delta == 0:
        return
    product.quantity = max(product.quantity + delta, 0)
    product.save(update_fields=["quantity", "updated_at"])


def branch_low_stock_queryset(branch):
    queryset = (
        product_queryset_for_branch(branch)
        .filter(branch_quantity__lte=F("reorder_level"))
        .order_by("branch_quantity", "name")
    )
    return queryset


def product_queryset_for_branch(branch, queryset=None):
    queryset = queryset or Product.objects.all()
    if branch is None:
        return queryset.annotate(branch_quantity=F("quantity"))

    branch_stock_quantity = BranchStock.objects.filter(
        product=OuterRef("pk"),
        branch=branch,
    ).values("quantity")[:1]
    return queryset.annotate(
        branch_quantity=Coalesce(Subquery(branch_stock_quantity, output_field=IntegerField()), Value(0))
    )
