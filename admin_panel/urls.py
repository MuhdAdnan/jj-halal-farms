from django.urls import path
from . import views

app_name = "admin_panel"

urlpatterns = [
    path("login/", views.admin_login, name="login"),
    path("", views.admin_dashboard, name="dashboard"),
    path("profile/", views.admin_profile, name="profile"),
    path("logout/", views.admin_logout, name="logout"),
    path("customers/", views.admin_customers, name="customers"),
    path("orders/", views.admin_orders, name="orders"),
    path("orders/<int:pk>/status/", views.update_order_status, name="update_order_status"),
    path("orders/<int:pk>/", views.admin_order_detail, name="order_detail"),
    path("products/", views.admin_products, name="products"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/toggle-status/", views.toggle_customer_status, name="toggle_customer_status"),

]
