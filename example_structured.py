"""
Example: getting structured JSON output instead of a chat conversation.

Useful once you want to feed results into a UI, spreadsheet, database,
or a price-tracking script instead of just reading prose.
"""

import json
from agent import ShoppingAssistant

if __name__ == "__main__":
    assistant = ShoppingAssistant()

    goal = "best noise-canceling headphones under $200"
    print(f"Researching: {goal}\n")

    result = assistant.ask_structured(goal)
    print(json.dumps(result, indent=2))
