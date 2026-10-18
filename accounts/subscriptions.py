import calendar

from .models import Business


def add_subscription_term(start_at, plan):
    """Add one calendar month or year while keeping the time and a valid day."""
    months = 1 if plan == Business.SubscriptionPlan.MONTHLY else 12
    month_index = start_at.month - 1 + months
    year = start_at.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_at.day, calendar.monthrange(year, month)[1])
    return start_at.replace(year=year, month=month, day=day)
