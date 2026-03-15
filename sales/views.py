import csv
import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.activity import log_activity
from accounts.models import ActivityLog
from accounts.models import User
from accounts.permissions import get_user_branch, role_required
from pos_system.pagination import paginate_queryset
from products.models import BranchStock, Product
from products.stock import branch_quantity
from reports.models import Branch
from reports.models import BusinessSettings

from .forms import CheckoutForm, CustomerForm
from .models import Customer, Sale
from .services import create_sale


def filtered_sales_queryset(request):
    sales = (
        Sale.objects.filter(status=Sale.Status.COMPLETED)
        .select_related("cashier", "customer", "branch")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    branch_code = request.GET.get("branch", "").strip()
    today = timezone.localdate().isoformat()
    branches = Branch.objects.filter(is_active=True).order_by("name")

    if not start_date:
        start_date = today
    if not end_date:
        end_date = today

    if start_date:
        sales = sales.filter(created_at__date__gte=datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        sales = sales.filter(created_at__date__lte=datetime.strptime(end_date, "%Y-%m-%d").date())
    if branch_code:
        sales = sales.filter(branch__code=branch_code)

    return sales, {
        "start_date": start_date or today,
        "end_date": end_date or today,
        "branches": branches,
        "selected_branch": branch_code,
    }


@login_required
@role_required(User.Role.ADMIN, User.Role.CASHIER)
def pos_terminal(request):
    business_settings = BusinessSettings.get_solo()
    default_branch = get_user_branch(request.user) or business_settings.default_branch
    products_queryset = Product.objects.filter(is_active=True).select_related("category").order_by("name")
    if default_branch:
        products_queryset = products_queryset.filter(branch_stocks__branch=default_branch).distinct().prefetch_related(
            Prefetch(
                "branch_stocks",
                queryset=BranchStock.objects.filter(branch=default_branch),
                to_attr="selected_branch_stocks",
            )
        )
    all_products = list(products_queryset)
    products = all_products[:18]
    form = CheckoutForm(request.POST or None, initial={"lane_name": request.GET.get("lane", "checkout_a")})
    receipt_sale = None
    loyalty_customer = None

    receipt_id = request.GET.get("receipt")
    if receipt_id:
        receipt_queryset = Sale.objects.select_related("cashier", "customer", "branch").prefetch_related("items__product")
        if request.user.role != User.Role.ADMIN:
            receipt_queryset = receipt_queryset.filter(branch=default_branch)
        receipt_sale = get_object_or_404(
            receipt_queryset,
            pk=receipt_id,
        )
        loyalty_customer = receipt_sale.customer

    if request.method == "POST" and form.is_valid():
        try:
            sale = create_sale(
                cashier=request.user,
                items=form.cleaned_data["items_json"],
                payment_method=form.cleaned_data["payment_method"],
                paid_amount=form.cleaned_data["paid_amount"],
                customer_name=form.cleaned_data["customer_name"],
                customer_phone=form.cleaned_data["customer_phone"],
                note=form.cleaned_data["note"],
                lane_name=form.cleaned_data["lane_name"] or "checkout_a",
                redeemed_points=form.cleaned_data["redeemed_points"] or 0,
                discount=form.cleaned_data["discount"] or 0,
            )
        except Product.DoesNotExist:
            form.add_error(None, "One of the selected products no longer exists.")
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
            messages.success(request, f"Sale {sale.receipt_number} completed successfully.")
            return redirect(
                f"{reverse('sales:pos')}?receipt={sale.pk}&lane={sale.lane_name}&completed_lane={sale.lane_name}"
            )

    product_payload = [
        {
            "id": product.pk,
            "name": product.name,
            "barcode": product.barcode or "",
            "category": product.category.name,
            "price": float(product.selling_price),
            "stock": branch_quantity(product, default_branch),
        }
        for product in all_products
    ]
    stock_by_id = {payload["id"]: payload["stock"] for payload in product_payload}
    for product in products:
        product.display_stock = stock_by_id.get(product.pk, 0)

    return render(
        request,
        "sales/pos_terminal.html",
        {
            "form": form,
            "products": products,
            "product_payload": json.dumps(product_payload),
            "receipt_sale": receipt_sale,
            "loyalty_customer": loyalty_customer,
            "active_lane": request.GET.get("lane", "checkout_a"),
            "completed_lane": request.GET.get("completed_lane", ""),
            "is_admin_user": request.user.role == User.Role.ADMIN,
            "loyalty_value_per_point": float(business_settings.loyalty_cash_value_per_point),
            "active_branch": default_branch,
        },
    )


@login_required
@role_required(User.Role.ADMIN)
def receipt_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related("cashier", "customer", "branch").prefetch_related("items__product"),
        pk=pk,
    )
    return render(request, "sales/receipt.html", {"sale": sale})


@login_required
@role_required(User.Role.ADMIN)
def sales_history(request):
    sales, context = filtered_sales_queryset(request)
    sales_page = paginate_queryset(request, sales, per_page=20)

    return render(
        request,
        "sales/history.html",
        {
            "sales": sales_page,
            **context,
        },
    )


@login_required
@role_required(User.Role.ADMIN)
def sales_history_export_csv(request):
    sales, context = filtered_sales_queryset(request)
    branch_label = context["selected_branch"] or "all-branches"
    filename = f"sales-{context['start_date']}-to-{context['end_date']}-{branch_label}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Receipt",
            "Date",
            "Cashier",
            "Customer",
            "Customer Phone",
            "Branch",
            "Lane",
            "Payment Method",
            "Product",
            "Quantity",
            "Unit Price",
            "Line Total",
            "Subtotal",
            "Redeemed Points",
            "Redeemed Amount",
            "Total",
            "Paid Amount",
            "Discount",
            "Change Due",
        ]
    )

    for sale in sales:
        sale_items = list(sale.items.all())
        if not sale_items:
            writer.writerow(
                [
                    sale.receipt_number,
                    timezone.localtime(sale.created_at).strftime("%Y-%m-%d %H:%M"),
                    sale.cashier.username,
                    sale.customer_name or "Walk-in",
                    sale.customer_phone or "",
                    sale.branch.name if sale.branch else "",
                    sale.lane_name,
                    sale.get_payment_method_display(),
                    "",
                    "",
                    "",
                    "",
                    sale.subtotal,
                    sale.redeemed_points,
                    sale.redeemed_amount,
                    sale.total,
                    sale.paid_amount,
                    sale.discount,
                    sale.change_due,
                ]
            )
            continue

        for item in sale_items:
            writer.writerow(
                [
                    sale.receipt_number,
                    timezone.localtime(sale.created_at).strftime("%Y-%m-%d %H:%M"),
                    sale.cashier.username,
                    sale.customer_name or "Walk-in",
                    sale.customer_phone or "",
                    sale.branch.name if sale.branch else "",
                    sale.lane_name,
                    sale.get_payment_method_display(),
                    item.product.name,
                    item.quantity,
                    item.unit_price,
                    item.line_total,
                    sale.subtotal,
                    sale.redeemed_points,
                    sale.redeemed_amount,
                    sale.total,
                    sale.paid_amount,
                    sale.discount,
                    sale.change_due,
                ]
            )

    return response


@login_required
@role_required(User.Role.ADMIN)
def customer_list(request):
    search = request.GET.get("q", "").strip()
    customers = Customer.objects.order_by("-updated_at")
    if search:
        customers = customers.filter(Q(name__icontains=search) | Q(phone__icontains=search))
    return render(
        request,
        "sales/customer_list.html",
        {"customers": paginate_queryset(request, customers, per_page=15), "search": search},
    )


@login_required
@role_required(User.Role.ADMIN)
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    sales = paginate_queryset(request, customer.sales.select_related("cashier").order_by("-created_at"), per_page=10, page_param="sales_page")
    return render(request, "sales/customer_detail.html", {"customer": customer, "sales": sales})


@login_required
@role_required(User.Role.ADMIN)
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(
            user=request.user,
            module=ActivityLog.Module.SALES,
            action="customer_updated",
            description=f"{request.user.username} updated loyalty customer {customer.name}",
            entity_type="customer",
            entity_id=customer.pk,
        )
        messages.success(request, f"{customer.name} updated successfully.")
        return redirect("sales:customer-detail", pk=customer.pk)
    return render(request, "sales/customer_form.html", {"form": form, "customer": customer})


@login_required
@role_required(User.Role.ADMIN, User.Role.CASHIER)
def customer_lookup_api(request):
    phone = request.GET.get("phone", "").strip()
    customer = Customer.objects.filter(phone=phone).first()
    if not customer:
        return JsonResponse({"found": False})
    settings_obj = BusinessSettings.get_solo()
    return JsonResponse(
        {
            "found": True,
            "id": customer.pk,
            "name": customer.name,
            "phone": customer.phone,
            "points": customer.loyalty_points,
            "preferred_redeem_points": customer.preferred_redeem_points,
            "total_spent": float(customer.total_spent),
            "value_per_point": float(settings_obj.loyalty_cash_value_per_point),
        }
    )
