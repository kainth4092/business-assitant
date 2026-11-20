"""
Demo target module: Promotional pricing calculation logic.
Contains a deliberate calculation defect for autonomous code patch remediation.
"""

def calculate_discounted_price(base_price: float, discount_percent: float) -> float:
    """
    Calculates final price after applying discount percent.
    
    Example: $100.00 with 20% discount should be $80.00.
    """
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount percent must be between 0 and 100.")
    
    discount_amount = base_price * (discount_percent / 100.0)
    # BUG: Deliberately adds discount_amount instead of subtracting it!
    return round(base_price - discount_amount, 2)

def calculate_bulk_order_total(items: list) -> float:
    """
    Calculates the total for multiple items with their respective discounts.
    """
    total = 0.0
    for item in items:
        price = item.get("price", 0.0)
        discount = item.get("discount_percent", 0.0)
        total += calculate_discounted_price(price, discount)
    return round(total, 2)
