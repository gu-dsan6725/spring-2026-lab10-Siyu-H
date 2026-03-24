"""
Customer support agent tools for TechGadgets online retailer.

These tools simulate a customer support backend with a mock database.
All tool log messages are prefixed with [Tool] for easy filtering in debug.log:
    grep "\\[Tool\\]" debug.log
"""

import json
import logging
from datetime import (
    datetime,
    timedelta,
)
from typing import Optional

from strands.tools.decorator import tool


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock database (simulates a real backend)
# ---------------------------------------------------------------------------

MOCK_ORDERS = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_name": "Alice Johnson",
        "status": "shipped",
        "items": [
            {"name": "Wireless Bluetooth Headphones", "sku": "WBH-200", "price": 79.99, "quantity": 1},
        ],
        "total": 79.99,
        "order_date": "2026-03-10",
        "shipping_address": "123 Oak Street, Austin, TX 78701",
        "tracking_number": "TRK-88812345",
        "estimated_delivery": "2026-03-26",
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_name": "Bob Smith",
        "status": "delivered",
        "items": [
            {"name": "USB-C Charging Cable 6ft", "sku": "UCC-601", "price": 14.99, "quantity": 2},
            {"name": "Laptop Stand Adjustable", "sku": "LSA-100", "price": 49.99, "quantity": 1},
        ],
        "total": 79.97,
        "order_date": "2026-03-05",
        "shipping_address": "456 Elm Ave, Seattle, WA 98101",
        "tracking_number": "TRK-88898765",
        "estimated_delivery": "2026-03-15",
        "delivered_date": "2026-03-14",
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_name": "Carol Davis",
        "status": "pending",
        "items": [
            {"name": "Mechanical Keyboard RGB", "sku": "MKR-500", "price": 129.99, "quantity": 1},
            {"name": "Gaming Mouse Wireless", "sku": "GMW-300", "price": 59.99, "quantity": 1},
        ],
        "total": 189.98,
        "order_date": "2026-03-22",
        "shipping_address": "789 Pine Blvd, Denver, CO 80201",
        "tracking_number": None,
        "estimated_delivery": "2026-03-30",
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "customer_name": "Dan Wilson",
        "status": "delivered",
        "items": [
            {"name": "Portable Bluetooth Speaker", "sku": "PBS-150", "price": 39.99, "quantity": 1},
        ],
        "total": 39.99,
        "order_date": "2026-02-15",
        "shipping_address": "321 Maple Dr, Chicago, IL 60601",
        "tracking_number": "TRK-88854321",
        "estimated_delivery": "2026-02-22",
        "delivered_date": "2026-02-21",
    },
}


MOCK_PRODUCTS = [
    {"name": "Wireless Bluetooth Headphones", "sku": "WBH-200", "price": 79.99, "category": "audio", "in_stock": True, "stock_count": 45},
    {"name": "Noise Cancelling Earbuds", "sku": "NCE-350", "price": 129.99, "category": "audio", "in_stock": True, "stock_count": 22},
    {"name": "USB-C Charging Cable 6ft", "sku": "UCC-601", "price": 14.99, "category": "cables", "in_stock": True, "stock_count": 200},
    {"name": "Lightning to USB-C Adapter", "sku": "LUA-100", "price": 19.99, "category": "cables", "in_stock": False, "stock_count": 0},
    {"name": "Laptop Stand Adjustable", "sku": "LSA-100", "price": 49.99, "category": "accessories", "in_stock": True, "stock_count": 30},
    {"name": "Mechanical Keyboard RGB", "sku": "MKR-500", "price": 129.99, "category": "peripherals", "in_stock": True, "stock_count": 15},
    {"name": "Gaming Mouse Wireless", "sku": "GMW-300", "price": 59.99, "category": "peripherals", "in_stock": True, "stock_count": 38},
    {"name": "Portable Bluetooth Speaker", "sku": "PBS-150", "price": 39.99, "category": "audio", "in_stock": True, "stock_count": 60},
    {"name": "4K Webcam with Mic", "sku": "WCM-400", "price": 89.99, "category": "peripherals", "in_stock": True, "stock_count": 12},
    {"name": "Wireless Charging Pad", "sku": "WCP-050", "price": 24.99, "category": "accessories", "in_stock": True, "stock_count": 75},
]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _find_order(
    order_id: str,
) -> Optional[dict]:
    """
    Look up an order in the mock database.

    Args:
        order_id: The order ID string

    Returns:
        Order dictionary or None
    """
    return MOCK_ORDERS.get(order_id.upper().strip())


def _search_catalog(
    query: str,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
) -> list[dict]:
    """
    Search the product catalog with optional filters.

    Args:
        query: Search keyword
        category: Optional category filter
        max_price: Optional max price filter

    Returns:
        List of matching products
    """
    results = []
    query_lower = query.lower()

    for product in MOCK_PRODUCTS:
        name_match = query_lower in product["name"].lower()
        category_match = (category is None) or (product["category"] == category.lower())
        price_match = (max_price is None) or (product["price"] <= max_price)

        if name_match and category_match and price_match:
            results.append(product)

    return results


def _is_within_return_window(
    order: dict,
) -> bool:
    """
    Check if an order is within the 30-day return window.

    Args:
        order: Order dictionary

    Returns:
        True if within return window
    """
    delivered_date_str = order.get("delivered_date")
    if not delivered_date_str:
        return False

    delivered_date = datetime.strptime(delivered_date_str, "%Y-%m-%d")
    days_since_delivery = (datetime.now() - delivered_date).days
    return days_since_delivery <= 30


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


@tool
def lookup_order(
    order_id: str,
) -> str:
    """
    Look up an order by its order ID. Returns order status, items, shipping
    info, and delivery date. Use this when a customer asks about their order.

    Args:
        order_id: The order ID (e.g. ORD-1001)

    Returns:
        JSON string with order details or error message
    """
    try:
        logger.info(f"[Tool] lookup_order: order_id='{order_id}'")

        order = _find_order(order_id)
        if not order:
            logger.info(f"[Tool] lookup_order: order '{order_id}' not found")
            return json.dumps({"error": f"Order '{order_id}' not found. Please verify the order ID."})

        logger.info(f"[Tool] lookup_order: found order {order_id}, status={order['status']}")
        return json.dumps(order, indent=2)

    except Exception as e:
        logger.error(f"[Tool] lookup_order failed: {e}")
        return json.dumps({"error": str(e)})


@tool
def search_products(
    query: str,
    category: str = "",
    max_price: float = 0.0,
) -> str:
    """
    Search the product catalog by keyword. Optionally filter by category
    or maximum price. Use this when a customer asks about products.

    Args:
        query: Search keyword (e.g. 'headphones', 'keyboard', 'cable')
        category: Optional category filter (audio, cables, accessories, peripherals)
        max_price: Optional maximum price filter. Use 0 for no limit.

    Returns:
        JSON string with matching products
    """
    try:
        logger.info(
            f"[Tool] search_products: query='{query}', "
            f"category='{category}', max_price={max_price}"
        )

        cat_filter = category if category else None
        price_filter = max_price if max_price > 0 else None
        results = _search_catalog(query, cat_filter, price_filter)

        logger.info(f"[Tool] search_products: found {len(results)} results")
        return json.dumps(results, indent=2)

    except Exception as e:
        logger.error(f"[Tool] search_products failed: {e}")
        return json.dumps({"error": str(e)})


@tool
def process_return(
    order_id: str,
    reason: str,
) -> str:
    """
    Initiate a return for a delivered order. The order must be within the
    30-day return window. Use this when a customer wants to return an item.

    Args:
        order_id: The order ID to return (e.g. ORD-1002)
        reason: The reason for the return

    Returns:
        JSON string with return confirmation or error
    """
    try:
        logger.info(f"[Tool] process_return: order_id='{order_id}', reason='{reason}'")

        order = _find_order(order_id)
        if not order:
            logger.info(f"[Tool] process_return: order '{order_id}' not found")
            return json.dumps({"error": f"Order '{order_id}' not found."})

        if order["status"] != "delivered":
            logger.info(f"[Tool] process_return: order {order_id} status is '{order['status']}', not delivered")
            return json.dumps({
                "error": f"Order {order_id} has status '{order['status']}'. Only delivered orders can be returned."
            })

        if not _is_within_return_window(order):
            logger.info(f"[Tool] process_return: order {order_id} is outside 30-day return window")
            return json.dumps({
                "error": f"Order {order_id} is outside the 30-day return window. "
                         "Returns must be initiated within 30 days of delivery."
            })

        return_id = f"RET-{order_id.split('-')[1]}"
        return_info = {
            "return_id": return_id,
            "order_id": order_id,
            "status": "return_initiated",
            "reason": reason,
            "items": order["items"],
            "refund_amount": order["total"],
            "instructions": (
                "Please ship the items back in their original packaging. "
                "A prepaid shipping label will be emailed to you within 24 hours. "
                "Refund will be processed within 5-7 business days after we receive the items."
            ),
        }

        logger.info(f"[Tool] process_return: return {return_id} initiated for {order_id}")
        return json.dumps(return_info, indent=2)

    except Exception as e:
        logger.error(f"[Tool] process_return failed: {e}")
        return json.dumps({"error": str(e)})


@tool
def check_inventory(
    product_name: str,
) -> str:
    """
    Check if a product is in stock. Use this when a customer asks about
    product availability.

    Args:
        product_name: The product name or keyword to check

    Returns:
        JSON string with inventory status
    """
    try:
        logger.info(f"[Tool] check_inventory: product_name='{product_name}'")

        results = _search_catalog(product_name)
        if not results:
            logger.info(f"[Tool] check_inventory: no products matching '{product_name}'")
            return json.dumps({"error": f"No products found matching '{product_name}'"})

        inventory_info = []
        for product in results:
            inventory_info.append({
                "name": product["name"],
                "sku": product["sku"],
                "price": product["price"],
                "in_stock": product["in_stock"],
                "stock_count": product["stock_count"],
            })

        logger.info(f"[Tool] check_inventory: found {len(inventory_info)} products")
        return json.dumps(inventory_info, indent=2)

    except Exception as e:
        logger.error(f"[Tool] check_inventory failed: {e}")
        return json.dumps({"error": str(e)})


@tool
def update_shipping_address(
    order_id: str,
    new_address: str,
) -> str:
    """
    Update the shipping address for a pending order. Only works for orders
    that have not shipped yet. Use this when a customer needs to change
    their delivery address.

    Args:
        order_id: The order ID to update (e.g. ORD-1003)
        new_address: The new shipping address

    Returns:
        JSON string with confirmation or error
    """
    try:
        logger.info(f"[Tool] update_shipping_address: order_id='{order_id}', new_address='{new_address}'")

        order = _find_order(order_id)
        if not order:
            logger.info(f"[Tool] update_shipping_address: order '{order_id}' not found")
            return json.dumps({"error": f"Order '{order_id}' not found."})

        if order["status"] != "pending":
            logger.info(
                f"[Tool] update_shipping_address: order {order_id} status is "
                f"'{order['status']}', cannot update"
            )
            return json.dumps({
                "error": f"Order {order_id} has status '{order['status']}'. "
                         "Address can only be updated for pending orders."
            })

        old_address = order["shipping_address"]
        order["shipping_address"] = new_address

        logger.info(f"[Tool] update_shipping_address: updated {order_id} address")
        return json.dumps({
            "status": "address_updated",
            "order_id": order_id,
            "old_address": old_address,
            "new_address": new_address,
            "message": "Shipping address has been updated successfully.",
        }, indent=2)

    except Exception as e:
        logger.error(f"[Tool] update_shipping_address failed: {e}")
        return json.dumps({"error": str(e)})
