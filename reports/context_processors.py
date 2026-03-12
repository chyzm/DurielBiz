from .models import BusinessSettings


def business_settings(request):
    return {"business_settings": BusinessSettings.get_solo()}
