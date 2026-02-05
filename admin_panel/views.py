from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.models import User
from products.models import Product
from orders.models import Order
from .models import AdminProfile
from .decorators import staff_required
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from accounts.models import CustomerMessage

User = get_user_model()

def is_admin(user):
    return user.is_authenticated and user.is_staff

# ---------------- Admin Authentication ----------------
def admin_login(request):
    """Admin login page."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_panel:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_panel:dashboard')
        messages.error(request, 'Invalid username or password')

    return render(request, 'admin_panel/login.html')


@staff_required
def admin_logout(request):
    """Logs out admin."""
    logout(request)
    messages.success(request, "You have successfully logged out.")
    return redirect('admin_panel:login')


# ---------------- Admin Dashboard ----------------
@staff_required
def admin_dashboard(request):
    """Admin dashboard overview."""
    recent_orders_qs = (
        Order.objects.select_related("user")
        .prefetch_related("items__product")
        .order_by("-created_at")[:5]
    )
    recent_orders = []
    for order in recent_orders_qs:
        item_summary = ", ".join(
            f"{item.product.name} (x{item.quantity})" for item in order.items.all()
        )
        customer_name = order.full_name or order.user.get_full_name() or order.user.username
        recent_orders.append(
            {
                "customer_name": customer_name,
                "items": item_summary or "-",
                "total": order.total_amount,
                "status_display": order.get_status_display(),
            }
        )

    context = {
        'total_products': Product.objects.count(),
        'total_orders': Order.objects.count(),
        'pending_orders': Order.objects.filter(status="pending").count(),
        'completed_orders': Order.objects.filter(status="completed").count(),
        'recent_orders': recent_orders,
    }
    return render(request, 'admin_panel/dashboard.html', context)

# ---------------- Admin Products ----------------
@staff_required
def admin_products(request):
    """Admin product list."""
    # Replace placeholder with real Product objects later
    products = Product.objects.all()
    context = {
        "products": products,
    }
    return render(request, 'admin_panel/products.html', context)





# ---------------- Admin Users ----------------
@staff_required
def admin_customers(request):
    search = request.GET.get("q", "")

    customers = User.objects.filter(is_staff=False)

    if search:
        customers = customers.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    customers = customers.annotate(
        total_orders=Count("orders")
    ).order_by("-date_joined")

    paginator = Paginator(customers, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search": search,
    }
    return render(request, "admin_panel/customers.html", context)


@staff_required
def toggle_customer_status(request, pk):
    user = get_object_or_404(User, pk=pk, is_staff=False)
    user.is_active = not user.is_active
    user.save()

    messages.success(
        request,
        f"Customer {'activated' if user.is_active else 'deactivated'} successfully."
    )
    return redirect("admin_panel:customers")

# ---------------- Customer Detail ----------------
@staff_required
def customer_detail(request, pk):
    # Get customer
    customer = get_object_or_404(User, pk=pk, is_staff=False)

    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        if body:
            CustomerMessage.objects.create(
                sender=request.user,
                recipient=customer,
                subject=subject,
                body=body,
            )
            messages.success(request, "Message sent to customer.")
            return redirect("admin_panel:customer_detail", pk=customer.pk)
        messages.error(request, "Message body cannot be empty.")

    # Get all orders for customer
    orders_list = (
        Order.objects.filter(user=customer)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    # Paginate orders(10 per page)
    paginator = Paginator(orders_list, 10)
    page_number = request.GET.get("page")
    orders = paginator.get_page(page_number)

    # Summary stats
    total_orders = orders_list.count()
    total_spent = orders_list.aggregate(total=Sum("total_amount"))["total"] or 0

    total_items_purchased = total_orders

    customer_phone = ""
    if hasattr(customer, "customerprofile"):
        customer_phone = customer.customerprofile.phone

    context = {
        "customer": customer,
        "orders": orders,
        "total_items_purchased": total_items_purchased,
        "total_orders": total_orders,
        "total_spent": total_spent,
        "customer_phone": customer_phone,
    }
    return render(request, "admin_panel/customer_detail.html", context)



# ---------------- Admin Orders ----------------
@staff_required
def admin_orders(request):
    """Admin orders overview."""
    orders_list = (
        Order.objects.select_related("user")
        .prefetch_related("items__product")
        .order_by("-created_at")
        .distinct()
    )
    paginator = Paginator(orders_list, 10)
    page_number = request.GET.get("page")
    orders = paginator.get_page(page_number)
    return render(
        request,
        "admin_panel/orders.html",
        {"orders": orders, "status_choices": Order.STATUS_CHOICES},
    )


@staff_required
def admin_order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__product"),
        pk=pk,
    )
    return render(request, "admin_panel/order_detail.html", {"order": order})


@staff_required
def update_order_status(request, pk):
    if request.method != "POST":
        return redirect("admin_panel:orders")
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get("status")
    valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    if new_status in valid_statuses:
        order.status = new_status
        order.save(update_fields=["status"])
        if new_status == "completed" and not order.stock_deducted:
            for item in order.items.select_related("product"):
                product = item.product
                product.stock = max(product.stock - item.quantity, 0)
                product.save(update_fields=["stock"])
            order.stock_deducted = True
            order.save(update_fields=["stock_deducted"])
        messages.success(request, "Order status updated.")
    else:
        messages.error(request, "Invalid status.")
    return redirect("admin_panel:orders")





# ---------------- Admin Profile ----------------
@staff_required
def admin_profile(request):
    """View and update admin profile."""
    profile, _ = AdminProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "business_name": "JJ Halal Farms",
            "phone": "",
            "location": "",
            "description": ""
        }
    )

    if request.method == "POST":
        profile.business_name = request.POST.get("business_name", profile.business_name)
        profile.phone = request.POST.get("phone", profile.phone)
        profile.location = request.POST.get("location", profile.location)
        profile.description = request.POST.get("description", profile.description)
        if request.FILES.get("avatar"):
            profile.avatar = request.FILES.get("avatar")
        profile.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("admin_panel:profile")

    return render(request, "admin_panel/profile.html", {"profile": profile})





# Index View
def index(request):
    return render(request, 'index.html')
