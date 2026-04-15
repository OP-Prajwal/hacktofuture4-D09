
def calculate_total(items):
    total = 0
    for item in items:
        # BUG: This will fail if item['price'] is missing or None
        total += item['price']
    return total

if __name__ == "__main__":
    # Simulate a production-like crash
    print("Starting payment processing...")
    cart = [
        {"name": "Laptop", "price": 1200},
        {"name": "Mouse", "price": None}, # This will trigger a TypeError
    ]
    print(f"Processing {len(cart)} items")
    result = calculate_total(cart)
    print(f"Total: {result}")
