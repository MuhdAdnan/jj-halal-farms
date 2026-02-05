def cart_count(request):
    cart = request.session.get("cart", {})
    total_qty = 0
    for qty in cart.values():
        try:
            total_qty += int(qty)
        except (TypeError, ValueError):
            continue
    return {"cart_count": total_qty}
