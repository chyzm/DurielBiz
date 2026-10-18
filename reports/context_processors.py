from .models import BusinessSettings
from accounts.tenancy import get_current_business_id, reset_current_business_id, set_current_business_id


def business_settings(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.business_id:
        return {"business_settings": None}
    if get_current_business_id() == user.business_id:
        return {"business_settings": BusinessSettings.get_solo()}
    token = set_current_business_id(user.business_id)
    try:
        settings = BusinessSettings.get_solo()
    finally:
        reset_current_business_id(token)
    return {"business_settings": settings}
