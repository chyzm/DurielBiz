import random
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import EmailOTP

OTP_VALIDITY_MINUTES = 10


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def create_otp(email: str, purpose: str) -> EmailOTP:
    email = email.strip().lower()
    EmailOTP.objects.filter(email__iexact=email, purpose=purpose, is_used=False).update(is_used=True)
    return EmailOTP.objects.create(
        email=email,
        code=generate_code(),
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES),
    )


def send_otp_email(otp: EmailOTP, *, subject: str, template_name: str) -> None:
    message = render_to_string(template_name, {"code": otp.code, "valid_minutes": OTP_VALIDITY_MINUTES})
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [otp.email], fail_silently=False)


def find_valid_otp(email: str, code: str, purpose: str) -> EmailOTP | None:
    otp = (
        EmailOTP.objects.filter(email__iexact=email.strip().lower(), purpose=purpose, code=code, is_used=False)
        .order_by("-created_at")
        .first()
    )
    return otp if otp and otp.is_valid() else None


def consume_otp(otp: EmailOTP) -> None:
    otp.is_used = True
    otp.save(update_fields=["is_used"])
