from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Document, InvoiceBusiness, ToolSubscription


def build_subscription_dates():
    started_at = timezone.now()
    expires_at = started_at + timedelta(hours=getattr(settings, "INVOICING_TRIAL_HOURS", 48))
    return started_at, expires_at


def create_initial_subscription(business: InvoiceBusiness) -> ToolSubscription:
    started_at, expires_at = build_subscription_dates()
    return ToolSubscription.objects.create(
        business=business,
        started_at=started_at,
        expires_at=expires_at,
        status=ToolSubscription.Status.TRIAL,
        plan_name="48-Hour Free Trial",
        has_paid_access=False,
    )


def due_for_expiry_notice():
    target_date = timezone.localdate() + timedelta(days=3)
    subscriptions = ToolSubscription.objects.select_related("business", "business__owner").filter(
        status=ToolSubscription.Status.ACTIVE,
        has_paid_access=True,
    )
    due_subscriptions = []
    for subscription in subscriptions:
        subscription.refresh_status()
        if subscription.status != ToolSubscription.Status.ACTIVE:
            continue
        if timezone.localtime(subscription.expires_at).date() != target_date:
            continue
        if subscription.reminder_sent_at and timezone.localtime(subscription.reminder_sent_at).date() >= timezone.localdate():
            continue
        due_subscriptions.append(subscription)
    return due_subscriptions


def send_expiry_notice(subscription: ToolSubscription):
    owner = subscription.business.owner
    if not owner.email:
        return False
    dashboard_url = f"{settings.DURIELBIZ_SITE_URL.rstrip('/')}/tools/dashboard/"
    subject = f"DurielBiz Tools subscription expires in 3 days for {subscription.business.name}"
    message = render_to_string(
        "invoicing/subscription_expiry_email.txt",
        {
            "business": subscription.business,
            "subscription": subscription,
            "dashboard_url": dashboard_url,
        },
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [owner.email], fail_silently=False)
    subscription.reminder_sent_at = timezone.now()
    subscription.save(update_fields=["reminder_sent_at", "updated_at"])
    return True


def render_document_pdf(document: Document) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    business = document.business
    story = []

    logo_cell = ""
    if business.logo:
        try:
            logo_cell = Image(business.logo.path, width=32 * mm, height=32 * mm)
        except Exception:
            logo_cell = ""

    business_lines = [f"<b>{business.name}</b>"]
    if business.address:
        business_lines.append(business.address.replace("\n", "<br/>"))
    if business.contact_phone:
        business_lines.append(business.contact_phone)
    if business.contact_email:
        business_lines.append(business.contact_email)

    header_table = Table(
        [[logo_cell, Paragraph("<br/>".join(business_lines), styles["BodyText"])]],
        colWidths=[38 * mm, 130 * mm],
    )
    story.append(header_table)
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>{document.get_document_type_display().upper()}</b>", styles["Title"]))
    story.append(Spacer(1, 8))

    details_table = Table(
        [
            ["Number", document.number, "Customer", document.customer_name],
            ["Issue Date", document.issue_date.strftime("%d %b %Y"), "Email", document.customer_email or "-"],
            ["Due Date", document.due_date.strftime("%d %b %Y") if document.due_date else "-", "Phone", document.customer_phone or "-"],
        ],
        colWidths=[28 * mm, 55 * mm, 28 * mm, 59 * mm],
    )
    details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(details_table)
    story.append(Spacer(1, 12))

    rows = [["Description", "Qty", "Unit Price", "Discount", "Line Total"]]
    for item in document.items.order_by("position", "id"):
        rows.append([item.description, f"{item.quantity:.2f}", f"{item.unit_price:.2f}", f"{item.discount_amount:.2f}", f"{item.line_total:.2f}"])

    item_table = Table(rows, colWidths=[76 * mm, 18 * mm, 24 * mm, 24 * mm, 24 * mm])
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(item_table)
    story.append(Spacer(1, 12))

    totals_table = Table(
        [
            ["Subtotal", f"{document.subtotal:.2f}"],
            ["Overall Discount", f"{document.discount_amount:.2f}"],
            ["Total", f"{document.total:.2f}"],
        ],
        colWidths=[45 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 2), (-1, 2), colors.whitesmoke),
            ]
        )
    )
    story.append(totals_table)

    if document.notes:
        story.append(Spacer(1, 14))
        story.append(Paragraph("<b>Notes</b>", styles["Heading4"]))
        story.append(Paragraph(document.notes.replace("\n", "<br/>"), styles["BodyText"]))

    story.append(Spacer(1, 28))

    def decorate_page(canvas, _doc):
        page_width, _page_height = A4

        if document.document_type == Document.DocumentType.RECEIPT:
            canvas.saveState()
            canvas.translate(page_width - 55 * mm, 250 * mm)
            canvas.rotate(18)
            canvas.setStrokeColor(colors.Color(0.25, 0.78, 0.45, alpha=0.45))
            canvas.setFillColor(colors.Color(0.25, 0.78, 0.45, alpha=0.18))
            canvas.setLineWidth(3)
            canvas.roundRect(-22 * mm, -8 * mm, 44 * mm, 16 * mm, 4 * mm, stroke=1, fill=1)
            canvas.setFillColor(colors.Color(0.10, 0.52, 0.24, alpha=0.65))
            canvas.setFont("Helvetica-Bold", 24)
            canvas.drawCentredString(0, -2 * mm, "PAID")
            canvas.restoreState()

        canvas.saveState()
        signature_right = page_width - 18 * mm
        signature_left = page_width - 70 * mm
        signature_y = 18 * mm
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(signature_left, signature_y + 10 * mm, signature_right, signature_y + 10 * mm)
        initials = document.effective_signature_initials
        if initials:
            canvas.setFont("Helvetica-Bold", 14)
            canvas.drawRightString(signature_right - 2 * mm, signature_y + 13 * mm, initials)
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(signature_right, signature_y + 5 * mm, "Signature")
        canvas.restoreState()

    pdf.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
    return buffer.getvalue()
