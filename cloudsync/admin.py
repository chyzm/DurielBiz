from django.contrib import admin

from .models import (
    Business,
    BusinessMembership,
    RemoteBranch,
    RemoteInventoryLog,
    RemotePurchase,
    RemotePurchaseItem,
    RemoteSale,
    RemoteSaleItem,
    SyncCredential,
    SyncEvent,
)


admin.site.register(Business)
admin.site.register(BusinessMembership)
admin.site.register(SyncCredential)
admin.site.register(RemoteBranch)
admin.site.register(RemoteSale)
admin.site.register(RemoteSaleItem)
admin.site.register(RemotePurchase)
admin.site.register(RemotePurchaseItem)
admin.site.register(RemoteInventoryLog)
admin.site.register(SyncEvent)
