"""
Price tracker: checks current prices for tracked products and reports
alerts when a price drops below the target or below the lowest price
ever recorded.

Run this file directly to check all tracked products for a user once
(e.g. from a cron job or a manual "check prices now" button):

    python price_tracker.py <user_id>
"""

import sys
import db
from agent import ShoppingAssistant
from notifications import notify_price_alert


def check_all_products(user_id: str, assistant: ShoppingAssistant = None, send_notifications: bool = True) -> list:
    """
    Checks the current price for every product a user is tracking.
    Returns a list of result dicts, each with an 'alert' flag and message.

    If send_notifications is True (default), any triggered alert is also
    sent via whichever channels (email/Telegram) are configured for the
    user — see notifications.py.
    """
    if assistant is None:
        assistant = ShoppingAssistant(user_id=user_id)

    products = db.list_tracked_products(user_id)
    results = []

    for product in products:
        check = assistant.check_current_price(product["search_query"])
        price = check.get("price")

        alert = False
        message = ""

        if price is None:
            message = f"Couldn't find a current price. {check.get('note', '')}"
        else:
            db.record_price_check(
                product["id"],
                price=price,
                source_url=check.get("source_url", ""),
                raw_note=check.get("note", ""),
            )

            lowest_before = db.get_lowest_price(product["id"])
            target = product.get("target_price")

            if target and price <= target:
                alert = True
                message = f"🎉 Price ${price} is at or below your target of ${target}!"
            elif lowest_before and price < lowest_before:
                alert = True
                message = f"📉 New lowest price seen: ${price} (previous lowest: ${lowest_before})"
            else:
                message = f"Current price: ${price}. No alert triggered."

        results.append({
            "product": product,
            "current_price": price,
            "alert": alert,
            "message": message,
            "source_url": check.get("source_url"),
        })

        if alert and send_notifications:
            notify_results = notify_price_alert(user_id, product["name"], message)
            results[-1]["notifications"] = notify_results

    return results


if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    db.init_db()

    print(f"Checking tracked products for user '{user_id}'...\n")
    results = check_all_products(user_id)

    if not results:
        print("No tracked products yet. Add some first!")
    else:
        for r in results:
            marker = "🔔" if r["alert"] else "  "
            print(f"{marker} {r['product']['name']}: {r['message']}")
            for n in r.get("notifications", []):
                status = "✅" if n["success"] else "❌"
                print(f"      {status} {n['channel']}: {n['detail']}")
