from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.core.mail import send_mail
from products.models import Product
from .models import Order, OrderItem
import uuid
import hmac
import json
import hashlib
import requests


def _get_cart(session):
    return session.setdefault("cart", {})


def _cart_totals(cart):
    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.objects.filter(id__in=product_ids)
    items = []
    total = Decimal("0.00")
    for product in products:
        quantity = int(cart.get(str(product.id), 0))
        line_total = product.price * quantity
        total += line_total
        items.append(
            {
                "product": product,
                "quantity": quantity,
                "line_total": line_total,
            }
        )
    return items, total


def _deduct_stock(order):
    if order.stock_deducted:
        return
    for item in order.items.select_related("product"):
        product = item.product
        product.stock = max(product.stock - item.quantity, 0)
        product.save(update_fields=["stock"])
    order.stock_deducted = True
    order.save(update_fields=["stock_deducted"])


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _reject_staff(request):
    if request.user.is_authenticated and request.user.is_staff:
        messages.error(request, "Admins cannot access customer pages.")
        return redirect("core:home")
    return None


def _order_items_summary(order):
    lines = []
    for item in order.items.select_related("product"):
        lines.append(f"- {item.product.name} x{item.quantity} @ ₦{item.price}")
    return "\n".join(lines) if lines else "- None"


def _send_order_notifications(order):
    subject = f"JJ Halal Farms Order #{order.id}"
    items_text = _order_items_summary(order)
    customer_name = order.full_name or order.user.get_full_name() or order.user.username
    customer_email = order.user.email
    admin_email = getattr(settings, "ADMIN_EMAIL", "") or settings.DEFAULT_FROM_EMAIL

    body = (
        f"Order ID: {order.id}\n"
        f"Customer: {customer_name}\n"
        f"Email: {customer_email}\n"
        f"Phone: {order.phone or '-'}\n"
        f"Delivery Method: {order.get_delivery_method_display()}\n"
        f"Address: {order.delivery_address or '-'}\n"
        f"Payment Method: {order.get_payment_method_display()}\n"
        f"Status: {order.get_status_display()}\n"
        f"Total: ₦{order.total_amount}\n"
        f"Items:\n{items_text}\n"
    )

    if customer_email:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [customer_email],
            fail_silently=True,
        )
    if admin_email:
        send_mail(
            f"[Admin] {subject}",
            body,
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
            fail_silently=True,
        )


def cart_view(request):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    cart = _get_cart(request.session)
    items, total = _cart_totals(cart)
    return render(request, "user/cart.html", {"items": items, "total": total})


def add_to_cart(request, product_id):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    product = get_object_or_404(Product, pk=product_id)
    cart = _get_cart(request.session)
    quantity = int(request.POST.get("quantity", 1))
    if product.stock <= 0:
        messages.error(request, f"{product.name} is out of stock.")
        return redirect(request.META.get("HTTP_REFERER", "orders:cart"))
    current = cart.get(str(product.id), 0)
    new_qty = min(current + max(quantity, 1), product.stock)
    cart[str(product.id)] = new_qty
    if new_qty != current + max(quantity, 1):
        messages.info(request, f"Only {product.stock} units available for {product.name}.")
    request.session.modified = True
    messages.success(request, f"{product.name} added to cart.")
    return redirect(request.META.get("HTTP_REFERER", "orders:cart"))


def update_cart(request, product_id):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    cart = _get_cart(request.session)
    quantity = int(request.POST.get("quantity", 1))
    if quantity <= 0:
        cart.pop(str(product_id), None)
    else:
        product = get_object_or_404(Product, pk=product_id)
        if product.stock <= 0:
            cart.pop(str(product_id), None)
            messages.error(request, f"{product.name} is out of stock.")
        else:
            cart[str(product_id)] = min(quantity, product.stock)
    request.session.modified = True
    return redirect("orders:cart")


def remove_from_cart(request, product_id):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    cart = _get_cart(request.session)
    cart.pop(str(product_id), None)
    request.session.modified = True
    return redirect("orders:cart")


@login_required(login_url="accounts:login")
def checkout(request):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    cart = _get_cart(request.session)
    items, total = _cart_totals(cart)
    if not items:
        messages.error(request, "Your cart is empty.")
        return redirect("orders:cart")
    for item in items:
        if item["quantity"] > item["product"].stock:
            cart[str(item["product"].id)] = item["product"].stock
            request.session.modified = True
            messages.error(
                request,
                f"{item['product'].name} stock reduced. Please review your cart.",
            )
            return redirect("orders:cart")

    if request.method == "POST":
        delivery_method = request.POST.get("delivery_method", "delivery")
        payment_method = request.POST.get("payment_method", "paystack")
        delivery_address = request.POST.get("delivery_address", "").strip()

        if delivery_method != "pickup" and payment_method == "pay_on_delivery":
            messages.error(request, "Pay on delivery is only available for farm pickup.")
            return redirect("orders:checkout")

        reference = uuid.uuid4().hex
        full_name = request.user.get_full_name().strip()
        if not full_name:
            full_name = request.user.first_name.strip()
        if not full_name:
            full_name = request.user.email or request.user.username
        phone = ""
        if hasattr(request.user, "customerprofile"):
            phone = request.user.customerprofile.phone

        order = Order.objects.create(
            user=request.user,
            full_name=full_name,
            phone=phone,
            delivery_method=delivery_method,
            payment_method=payment_method,
            delivery_address=delivery_address,
            total_amount=total,
            status="awaiting_payment" if payment_method == "pay_on_delivery" else "pending",
            payment_reference=reference,
        )

        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item["product"],
                quantity=item["quantity"],
                price=item["product"].price,
            )

        _send_order_notifications(order)

        request.session["cart"] = {}
        request.session.modified = True

        if payment_method == "pay_on_delivery":
            messages.success(request, "Order placed. Please pay on pickup.")
            return redirect("orders:order_history")

        if not settings.PAYSTACK_SECRET_KEY:
            messages.error(
                request,
                "Payment is not configured. Set PAYSTACK_SECRET_KEY in your .env file.",
            )
            return redirect("orders:cart")

        callback_url = request.build_absolute_uri(reverse("orders:paystack_verify"))
        payload = {
            "email": request.user.email,
            "amount": int(total * Decimal("100")),
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "order_id": order.id,
                "user_id": request.user.id,
            },
        }
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        try:
            response = requests.post(
                "https://api.paystack.co/transaction/initialize",
                json=payload,
                headers=headers,
                timeout=20,
            )
            data = response.json()
        except requests.RequestException:
            messages.error(request, "Payment service is unreachable. Please try again.")
            return redirect("orders:cart")
        if not data.get("status"):
            messages.error(request, data.get("message", "Payment initialization failed."))
            return redirect("orders:cart")

        return redirect(data["data"]["authorization_url"])

    profile_phone = ""
    if hasattr(request.user, "customerprofile"):
        profile_phone = request.user.customerprofile.phone

    return render(
        request,
        "user/checkout.html",
        {"items": items, "total": total, "profile_phone": profile_phone},
    )


@login_required(login_url="accounts:login")
def paystack_verify(request):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    reference = request.GET.get("reference")
    if not reference:
        messages.error(request, "Missing payment reference.")
        return redirect("orders:payment_failed")

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    try:
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=headers,
            timeout=20,
        )
        data = response.json()
    except requests.RequestException:
        messages.error(request, "Payment verification failed. Please try again.")
        return redirect("orders:payment_failed")
    if not data.get("status"):
        messages.error(request, "Payment verification failed.")
        return redirect("orders:payment_failed")

    paystack_data = data.get("data", {})
    if paystack_data.get("status") == "success":
        try:
            order = Order.objects.get(payment_reference=reference, user=request.user)
        except Order.DoesNotExist:
            messages.error(request, "Order not found for this payment.")
            return redirect("orders:payment_failed")

        if order.payment_method != "paystack":
            messages.error(request, "Payment method mismatch.")
            return redirect("orders:payment_failed")

        if paystack_data.get("amount") != int(order.total_amount * Decimal("100")):
            order.status = "failed"
            order.save(update_fields=["status"])
            messages.error(request, "Payment amount mismatch.")
            return redirect("orders:payment_failed")
        metadata = paystack_data.get("metadata", {})
        meta_order_id = _parse_int(metadata.get("order_id"))
        meta_user_id = _parse_int(metadata.get("user_id"))
        if meta_order_id != order.id or meta_user_id != order.user_id:
            order.status = "failed"
            order.save(update_fields=["status"])
            messages.error(request, "Payment metadata mismatch.")
            return redirect("orders:payment_failed")

        order.status = "completed"
        order.payment_verified_at = timezone.now()
        order.save(update_fields=["status", "payment_verified_at"])
        _deduct_stock(order)
        request.session["cart"] = {}
        request.session.modified = True
        return redirect("orders:payment_success")

    try:
        order = Order.objects.get(payment_reference=reference, user=request.user)
        order.status = "failed"
        order.save(update_fields=["status"])
    except Order.DoesNotExist:
        pass

    messages.error(request, "Payment was not successful.")
    return redirect("orders:payment_failed")


@csrf_exempt
def paystack_webhook(request):
    signature = request.headers.get("x-paystack-signature", "")
    if not signature or not settings.PAYSTACK_SECRET_KEY:
        return HttpResponse(status=400)

    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        request.body,
        hashlib.sha512,
    ).hexdigest()
    if not hmac.compare_digest(computed, signature):
        return HttpResponse(status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event = payload.get("event")
    data = payload.get("data", {})
    reference = data.get("reference")

    if event == "charge.success" and reference:
        try:
            order = Order.objects.get(payment_reference=reference)
        except Order.DoesNotExist:
            return HttpResponse(status=404)

        if order.payment_method != "paystack":
            return HttpResponse(status=400)

        if data.get("amount") != int(order.total_amount * Decimal("100")):
            return HttpResponse(status=400)
        metadata = data.get("metadata", {})
        meta_order_id = _parse_int(metadata.get("order_id"))
        meta_user_id = _parse_int(metadata.get("user_id"))
        if meta_order_id != order.id or meta_user_id != order.user_id:
            return HttpResponse(status=400)

        if order.status != "completed":
            order.status = "completed"
            order.payment_verified_at = timezone.now()
            order.save(update_fields=["status", "payment_verified_at"])
            _deduct_stock(order)

    return HttpResponse(status=200)


@login_required(login_url="accounts:login")
def payment_success(request):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    return render(request, "user/payment_success.html")


@login_required(login_url="accounts:login")
def payment_failed(request):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    return render(request, "user/payment_failed.html")


@login_required(login_url="accounts:login")
def order_history(request):
    staff_redirect = _reject_staff(request)
    if staff_redirect:
        return staff_redirect
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    return render(request, "user/order_history.html", {"orders": orders})