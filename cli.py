"""
Command-line interface for the Research & Shopping Assistant.

Usage:
    python cli.py [user_id]

Commands (type these instead of a research query):
    reset               - start a new chat session (keeps memory/tracking)
    remember <k>=<v>    - save a preference, e.g. remember budget=under $150
    forget <k>          - remove a saved preference
    prefs               - show saved preferences
    notify email=<addr>          - set your alert email
    notify telegram=<chat_id>    - set your alert Telegram chat id
    testnotify                    - send a test alert to your configured channels
    track <name> | <search query> | <target price optional>
                        - start tracking a product's price
                          e.g. track Sony XM5 | Sony WH-1000XM5 price | 250
    tracked             - list tracked products
    checkprices         - check current prices for all tracked products
    multi <goal>        - run multi-source research (retail+community+expert)
    quit / exit         - leave

Anything else is treated as a normal research/shopping question.
"""

import sys
import json
from agent import ShoppingAssistant
import db
from price_tracker import check_all_products


def main():
    user_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    db.init_db()

    print("=" * 60)
    print("  Research & Shopping Assistant")
    print(f"  User: {user_id}")
    print("  Type 'quit' to exit. See file header for all commands.")
    print("=" * 60)

    assistant = ShoppingAssistant(user_id=user_id)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("quit", "exit"):
            print("Bye!")
            break

        if lower == "reset":
            assistant.reset()
            print("(Started a new research session)")
            continue

        if lower == "prefs":
            prefs = assistant.preferences()
            if not prefs:
                print("No preferences saved yet.")
            else:
                for k, v in prefs.items():
                    print(f"  {k}: {v}")
            continue

        if lower.startswith("remember "):
            body = user_input[len("remember "):]
            if "=" not in body:
                print("Usage: remember <key>=<value>  e.g. remember budget=under $150")
                continue
            k, v = body.split("=", 1)
            assistant.remember(k.strip(), v.strip())
            print(f"(Remembered: {k.strip()} = {v.strip()})")
            continue

        if lower.startswith("forget "):
            k = user_input[len("forget "):].strip()
            assistant.forget(k)
            print(f"(Forgot: {k})")
            continue

        if lower.startswith("notify "):
            body = user_input[len("notify "):].strip()
            if "=" not in body:
                print("Usage: notify email=<addr>  OR  notify telegram=<chat_id>")
                continue
            k, v = body.split("=", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "email":
                assistant.remember("notify_email", v)
                print(f"(Alert email set to {v})")
            elif k == "telegram":
                assistant.remember("notify_telegram_chat_id", v)
                print(f"(Alert Telegram chat id set to {v})")
            else:
                print("Usage: notify email=<addr>  OR  notify telegram=<chat_id>")
            continue

        if lower == "testnotify":
            from notifications import notify_price_alert
            print("Sending test notification...")
            results = notify_price_alert(user_id, "Test Product", "This is a test alert. If you got this, notifications are working!")
            for n in results:
                status = "✅" if n["success"] else "❌"
                print(f"  {status} {n['channel']}: {n['detail']}")
            continue

        if lower.startswith("track "):
            body = user_input[len("track "):]
            parts = [p.strip() for p in body.split("|")]
            if len(parts) < 2:
                print("Usage: track <name> | <search query> | <target price optional>")
                continue
            name, query = parts[0], parts[1]
            target = None
            if len(parts) > 2 and parts[2]:
                try:
                    target = float(parts[2])
                except ValueError:
                    print("Target price must be a number, ignoring it.")
            pid = db.add_tracked_product(user_id, name, query, target)
            print(f"(Now tracking '{name}', product id {pid})")
            continue

        if lower == "tracked":
            products = db.list_tracked_products(user_id)
            if not products:
                print("No tracked products yet.")
            else:
                for p in products:
                    target = f"target ${p['target_price']}" if p["target_price"] else "no target"
                    print(f"  [{p['id']}] {p['name']} ({target}) - query: {p['search_query']}")
            continue

        if lower == "checkprices":
            print("\nChecking current prices...\n")
            results = check_all_products(user_id, assistant)
            if not results:
                print("No tracked products yet.")
            for r in results:
                marker = "🔔" if r["alert"] else "  "
                print(f"{marker} {r['product']['name']}: {r['message']}")
                for n in r.get("notifications", []):
                    status = "✅" if n["success"] else "❌"
                    print(f"      {status} {n['channel']}: {n['detail']}")
            continue

        if lower.startswith("multi "):
            goal = user_input[len("multi "):]
            print("\nRunning multi-source research (retail + community + expert)...\n")
            try:
                result = assistant.multi_source_research(goal)
                result.pop("_raw_findings", None)  # keep CLI output clean
                print(json.dumps(result, indent=2))
            except Exception as e:
                print(f"Error: {e}")
            continue

        # Default: normal chat/research turn
        print("\nSearching and thinking...\n")
        try:
            reply = assistant.ask(user_input)
            print(f"Assistant:\n{reply}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
