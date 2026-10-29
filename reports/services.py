from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from notifications.services import expiring_products_queryset, low_stock_products_queryset
from sales.models import Sale, SaleItem

from .models import BusinessSettings


def _date_bounds(day):
    current_timezone = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(day, time.min), current_timezone)
    end_at = timezone.make_aware(datetime.combine(day, time.max), current_timezone)
    return start_at, end_at


def _percent_change(current, previous):
    if not previous:
        return None
    return float((current - previous) / previous * 100)


def dashboard_metrics(*, branch=None):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    sales_filter = {"status": Sale.Status.COMPLETED}
    if branch is not None:
        sales_filter["branch"] = branch

    today_start, today_end = _date_bounds(today)
    yesterday_start, yesterday_end = _date_bounds(yesterday)
    sales_today = Sale.objects.filter(created_at__gte=today_start, created_at__lte=today_end, **sales_filter)
    sales_yesterday = Sale.objects.filter(created_at__gte=yesterday_start, created_at__lte=yesterday_end, **sales_filter)

    revenue_today = sales_today.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    revenue_yesterday = sales_yesterday.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    profit_today = (
        SaleItem.objects.filter(sale__in=sales_today).aggregate(total=Sum("profit"))["total"] or Decimal("0.00")
    )
    profit_yesterday = (
        SaleItem.objects.filter(sale__in=sales_yesterday).aggregate(total=Sum("profit"))["total"] or Decimal("0.00")
    )
    sales_count = sales_today.count()

    top_products_queryset = SaleItem.objects.filter(
        sale__created_at__gte=today_start,
        sale__created_at__lte=today_end,
        sale__status=Sale.Status.COMPLETED,
    )
    if branch is not None:
        top_products_queryset = top_products_queryset.filter(sale__branch=branch)
    top_products = (
        top_products_queryset
        .values("product__name")
        .annotate(quantity_sold=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-quantity_sold")
    )
    top_categories = (
        top_products_queryset
        .values("product__category__name")
        .annotate(revenue=Sum("line_total"))
        .order_by("-revenue")[:5]
    )

    last_week_start, _ = _date_bounds(today - timedelta(days=6))
    _, today_end = _date_bounds(today)
    last_week_queryset = Sale.objects.filter(status=Sale.Status.COMPLETED, created_at__gte=last_week_start, created_at__lte=today_end)
    if branch is not None:
        last_week_queryset = last_week_queryset.filter(branch=branch)

    last_week = (
        last_week_queryset
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total"), count=Count("id"))
        .order_by("day")
    )

    expiring_products = expiring_products_queryset()
    if branch is not None:
        expiring_products = expiring_products.filter(branch_stocks__branch=branch).distinct()

    return {
        "revenue_today": revenue_today,
        "revenue_change_pct": _percent_change(revenue_today, revenue_yesterday),
        "profit_today": profit_today,
        "profit_change_pct": _percent_change(profit_today, profit_yesterday),
        "sales_count": sales_count,
        "top_products": top_products,
        "top_categories": top_categories,
        "low_stock": low_stock_products_queryset(branch=branch),
        "expiring_products": expiring_products,
        "selected_branch_name": branch.name if branch else "All Branches",
        "sales_chart": {
            "labels": [item["day"].strftime("%d %b") for item in last_week],
            "values": [float(item["total"] or 0) for item in last_week],
        },
    }


def category_sales_report(*, branch=None, start_date=None, end_date=None):
    queryset = SaleItem.objects.filter(sale__status=Sale.Status.COMPLETED)
    if branch is not None:
        queryset = queryset.filter(sale__branch=branch)
    if start_date:
        start_at, _ = _date_bounds(start_date)
        queryset = queryset.filter(sale__created_at__gte=start_at)
    if end_date:
        _, end_at = _date_bounds(end_date)
        queryset = queryset.filter(sale__created_at__lte=end_at)
    return (
        queryset.values("product__category__name")
        .annotate(quantity_sold=Sum("quantity"), revenue=Sum("line_total"), profit=Sum("profit"))
        .order_by("-revenue")
    )


def profit_by_product_report(*, branch=None, start_date=None, end_date=None):
    queryset = SaleItem.objects.filter(sale__status=Sale.Status.COMPLETED)
    if branch is not None:
        queryset = queryset.filter(sale__branch=branch)
    if start_date:
        start_at, _ = _date_bounds(start_date)
        queryset = queryset.filter(sale__created_at__gte=start_at)
    if end_date:
        _, end_at = _date_bounds(end_date)
        queryset = queryset.filter(sale__created_at__lte=end_at)
    return (
        queryset.values("product__id", "product__name", "product__category__name")
        .annotate(quantity_sold=Sum("quantity"), revenue=Sum("line_total"), profit=Sum("profit"))
        .order_by("-profit")
    )


def render_profit_report_pdf(rows, *, branch_name, start_date, end_date):
    from io import BytesIO

    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Profit by Product", styles["Title"]),
        Paragraph(f"{branch_name} | {start_date} to {end_date}", styles["Normal"]),
        Spacer(1, 12),
    ]

    table_rows = [["Product", "Category", "Qty Sold", "Revenue", "Profit"]]
    for row in rows:
        table_rows.append(
            [
                row["product__name"],
                row["product__category__name"] or "—",
                str(row["quantity_sold"] or 0),
                f"{row['revenue'] or 0:.2f}",
                f"{row['profit'] or 0:.2f}",
            ]
        )

    table = Table(table_rows, colWidths=[55 * mm, 35 * mm, 25 * mm, 30 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(table)
    pdf.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="profit-by-product-{start_date}-to-{end_date}.pdf"'
    return response


def current_branch():
    return BusinessSettings.get_solo().default_branch
