from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .services import expiring_products_queryset


@login_required
def expiring_products_api(request):
    payload = [
        {
            "id": product.pk,
            "name": product.name,
            "expiry_date": product.expiry_date.isoformat() if product.expiry_date else None,
            "stock": product.quantity,
        }
        for product in expiring_products_queryset()[:10]
    ]
    return JsonResponse(payload, safe=False)
