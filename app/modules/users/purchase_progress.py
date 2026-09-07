def purchase_status(products: list[dict], *, registered: bool, complete: bool) -> str:
    """Keep registration completion separate from aggregate order settlement."""
    orders = [product for product in products if product.get("source") == "order"]
    def is_paid(product):
        return product.get("order_status") == "paid" and product.get("is_payment_complete") is not False

    if any(not is_paid(product) for product in orders):
        return "payment_pending"
    if any(is_paid(product) for product in orders):
        return "completed" if complete else "paid_profile_incomplete"
    if products or registered:
        return "selected"
    return "not_selected"
