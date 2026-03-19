from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify


def validate_logo_size(file_obj):
    max_bytes = 1024 * 1024
    if file_obj and getattr(file_obj, "size", 0) > max_bytes:
        raise ValidationError("Logo size must not exceed 1 MB.")


def validate_logo_extension(file_obj):
    allowed_extensions = (".png", ".jpg", ".jpeg")
    filename = getattr(file_obj, "name", "").lower()
    if filename and not filename.endswith(allowed_extensions):
        raise ValidationError("Upload a PNG or JPG logo file.")


def business_logo_upload_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"invoicing/logos/{instance.slug}.{extension}"


class InvoiceBusiness(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoice_business",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    logo = models.FileField(
        upload_to=business_logo_upload_path,
        blank=True,
        validators=[validate_logo_size, validate_logo_extension],
    )
    next_invoice_sequence = models.PositiveIntegerField(default=1)
    next_receipt_sequence = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def short_code(self):
        slug_source = (self.slug or slugify(self.name) or "biz").replace("-", "")
        return (slug_source[:6] or "BIZ").upper()

    @property
    def subscription(self):
        return getattr(self, "tool_subscription", None)

    def has_active_subscription(self):
        subscription = self.subscription
        if subscription is None:
            return False
        subscription.refresh_status()
        return subscription.is_access_active

    def issue_document_number(self, document_type):
        counter_field = "next_invoice_sequence" if document_type == "invoice" else "next_receipt_sequence"
        prefix = "INV" if document_type == "invoice" else "RCT"
        with transaction.atomic():
            business = InvoiceBusiness.objects.select_for_update().get(pk=self.pk)
            sequence = getattr(business, counter_field)
            setattr(business, counter_field, sequence + 1)
            business.save(update_fields=[counter_field, "updated_at"])
        return f"{self.short_code}-{prefix}-{sequence:06d}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.contact_email:
            self.contact_email = self.owner.email
        super().save(*args, **kwargs)


class ToolSubscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "48-Hour Trial"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        SUSPENDED = "suspended", "Suspended"

    business = models.OneToOneField(InvoiceBusiness, on_delete=models.CASCADE, related_name="tool_subscription")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    plan_name = models.CharField(max_length=80, default="48-Hour Free Trial")
    has_paid_access = models.BooleanField(default=False)
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["expires_at"]

    def __str__(self):
        return f"{self.business.name} - {self.get_status_display()}"

    @property
    def days_remaining(self):
        delta = timezone.localtime(self.expires_at).date() - timezone.localdate()
        return delta.days

    @property
    def is_access_active(self):
        self.refresh_status(save=False)
        return self.status in {self.Status.TRIAL, self.Status.ACTIVE} and self.expires_at >= timezone.now()

    @property
    def is_trial(self):
        self.refresh_status(save=False)
        return self.status == self.Status.TRIAL and not self.has_paid_access

    def refresh_status(self, save=True):
        expected_status = self.status
        if self.status != self.Status.SUSPENDED:
            if self.expires_at < timezone.now():
                expected_status = self.Status.EXPIRED
            else:
                expected_status = self.Status.ACTIVE if self.has_paid_access else self.Status.TRIAL
        if save and expected_status != self.status:
            self.status = expected_status
            self.save(update_fields=["status", "updated_at"])
        else:
            self.status = expected_status
        return self.status

    def activate_paid_cycle(self, commit=True):
        base_time = self.expires_at if self.expires_at > timezone.now() else timezone.now()
        self.started_at = timezone.now()
        self.expires_at = base_time + timedelta(days=30)
        self.status = self.Status.ACTIVE
        self.plan_name = "30-Day Paid Subscription"
        self.has_paid_access = True
        self.reminder_sent_at = None
        if commit:
            self.save()


class ServiceItem(models.Model):
    business = models.ForeignKey(InvoiceBusiness, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("business", "name")]

    def __str__(self):
        return self.name


class Document(models.Model):
    class DocumentType(models.TextChoices):
        INVOICE = "invoice", "Invoice"
        RECEIPT = "receipt", "Receipt"

    business = models.ForeignKey(InvoiceBusiness, on_delete=models.CASCADE, related_name="documents")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_documents",
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    number = models.CharField(max_length=40)
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=30, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("business", "number")]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.business.issue_document_number(self.document_type)
        super().save(*args, **kwargs)

    def recalculate_totals(self, commit=True):
        subtotal = Decimal("0.00")
        for item in self.items.order_by("position", "id"):
            base_total = ((item.quantity or Decimal("0.00")) * (item.unit_price or Decimal("0.00"))).quantize(Decimal("0.01"))
            discount = min((item.discount_amount or Decimal("0.00")).quantize(Decimal("0.01")), base_total)
            item.discount_amount = discount
            item.line_total = (base_total - discount).quantize(Decimal("0.01"))
            if commit:
                item.save(update_fields=["discount_amount", "line_total"])
            subtotal += item.line_total
        subtotal = subtotal.quantize(Decimal("0.01"))
        self.subtotal = subtotal
        document_discount = min((self.discount_amount or Decimal("0.00")).quantize(Decimal("0.01")), subtotal)
        self.discount_amount = document_discount
        self.total = (subtotal - document_discount).quantize(Decimal("0.01"))
        if commit:
            self.save(update_fields=["discount_amount", "subtotal", "total", "updated_at"])
        return self.total


class DocumentItem(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey(ServiceItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="document_items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        base_total = ((self.quantity or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))).quantize(Decimal("0.01"))
        discount = min((self.discount_amount or Decimal("0.00")).quantize(Decimal("0.01")), base_total)
        self.discount_amount = discount
        self.line_total = (base_total - discount).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
