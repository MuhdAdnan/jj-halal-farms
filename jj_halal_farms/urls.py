from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # CORE / PUBLIC
    path("", include("core.urls")),

    # USER AUTH
    path("auth/", include("accounts.urls")),
    # USER ORDERS
    path("orders/", include("orders.urls")),
    # ADMIN PANEL
    path("admin/", include("admin_panel.urls", namespace="admin_panel")),

    path("admin/products/", include("products.urls")),
    path("admin/orders/", include("orders.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
