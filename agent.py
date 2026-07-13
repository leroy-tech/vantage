"""
Research & Shopping Assistant
------------------------------
A simple agentic AI that:
1. Takes a shopping/research goal from the user
2. Searches the web using Claude's built-in web search tool
3. Reasons about the results and compares options
4. Returns a structured recommendation with sources
5. Supports multi-turn refinement ("actually, I need something for gym use")

This is intentionally kept simple and readable so you can see exactly
how an agent loop works before adding complexity.
"""

import os
import json
import re
from anthropic import Anthropic

import db
from config import get_secret

MODEL = "claude-sonnet-5"

BASE_SYSTEM_PROMPT = """You are a careful, honest shopping and research assistant.

When given a goal, you should:
1. Search the web for current, relevant information.
2. Compare at least 3 real options when the goal involves choosing a product.
3. Be explicit about trade-offs (price vs quality, pros vs cons).
4. Never invent prices, specs, or reviews — only state what you found.
5. If information is uncertain or conflicting, say so plainly.

When you give a final recommendation, structure it clearly with:
- A short summary (1-2 sentences)
- A ranked list of options with price, pros, cons
- Sources

Keep responses concise and skimmable. Use plain language, not marketing speak.
"""


class ShoppingAssistant:
    """Wraps a multi-turn conversation with Claude + web search tool.

    Pass a user_id to enable persistent memory: remembered preferences
    (budget, brand, must-have features) get folded into the system prompt
    automatically on every request.
    """

    def __init__(self, user_id: str = "default"):
        api_key = get_secret("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not found. Copy .env.example to .env and add your "
                "key (local use), or add it to Streamlit secrets (cloud deployment)."
            )
        self.client = Anthropic(api_key=api_key)
        self.history = []
        self.user_id = user_id
        db.init_db()

    # ---------- Memory ----------

    def _system_prompt(self) -> str:
        """Base prompt + any remembered preferences for this user."""
        prefs = db.get_preferences(self.user_id)
        if not prefs:
            return BASE_SYSTEM_PROMPT
        pref_lines = "\n".join(f"- {k}: {v}" for k, v in prefs.items())
        return (
            BASE_SYSTEM_PROMPT
            + f"\n\nKnown preferences for this user (apply them unless they "
              f"explicitly say otherwise this time):\n{pref_lines}\n"
        )

    def remember(self, key: str, value: str):
        """Explicitly store a preference, e.g. remember('budget', 'under $150')."""
        db.set_preference(self.user_id, key, value)

    def forget(self, key: str):
        db.delete_preference(self.user_id, key)

    def preferences(self) -> dict:
        return db.get_preferences(self.user_id)

    # ---------- Chat ----------

    def ask(self, user_message: str) -> str:
        """Send a message, get back the assistant's text reply, keep history."""
        self.history.append({"role": "user", "content": user_message})

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=self._system_prompt(),
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=self.history,
        )

        # Pull out just the text parts (search results/citations are handled
        # internally by the API and folded into the text with citations).
        text_parts = [block.text for block in response.content if block.type == "text"]
        reply = "\n".join(text_parts).strip()

        self.history.append({"role": "assistant", "content": reply})
        return reply

    def ask_structured(self, goal: str) -> dict:
        """
        One-shot structured version: asks Claude to research a goal and
        return JSON instead of prose. Useful if you want to feed the result
        into another program (e.g. a UI, a spreadsheet, a price tracker).
        """
        prompt = f"""Research this goal: {goal}

Search the web and respond with ONLY valid JSON (no markdown fences, no
extra text) in exactly this shape:

{{
  "summary": "one or two sentence summary",
  "recommendations": [
    {{
      "rank": 1,
      "name": "product or option name",
      "price": "approximate price or range",
      "pros": ["...", "..."],
      "cons": ["...", "..."],
      "source_url": "..."
    }}
  ]
}}
"""
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=self._system_prompt(),
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        text_parts = [block.text for block in response.content if block.type == "text"]
        raw = "\n".join(text_parts).strip()
        return _parse_json_response(raw)

    def reset(self):
        """Clear conversation history to start a fresh research session."""
        self.history = []

    # ---------- Multi-source research ----------

    def multi_source_research(self, goal: str) -> dict:
        """
        Runs three separate, source-focused searches (retail listings,
        community/forum opinion, and expert reviews) and then asks Claude
        to synthesize them into one final recommendation.

        This tends to give better-grounded answers than a single generic
        search because each sub-search has a narrower, clearer job.
        """
        sources = {
            "retail": (
                f"Search specifically for current retail listings and prices for: {goal}. "
                f"Focus on sites like Amazon, manufacturer sites, and major retailers. "
                f"List real products with real current prices you find."
            ),
            "community": (
                f"Search specifically for community opinions and discussion about: {goal}. "
                f"Focus on Reddit threads, forums, and user discussions. "
                f"Summarize what real users say are the pros/cons, common complaints, "
                f"and hidden gems that don't show up in official marketing."
            ),
            "expert": (
                f"Search specifically for expert/professional reviews about: {goal}. "
                f"Focus on dedicated review sites (e.g. RTINGS, Wirecutter, The Verge, "
                f"CNET, or category-specific expert outlets). "
                f"Summarize their tested findings, measurements, and rankings."
            ),
        }

        findings = {}
        for label, prompt in sources.items():
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1200,
                system=self._system_prompt(),
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )
            text_parts = [b.text for b in response.content if b.type == "text"]
            findings[label] = "\n".join(text_parts).strip()

        synthesis_prompt = f"""You previously gathered research from three angles on
this goal: {goal}

--- Retail/pricing findings ---
{findings['retail']}

--- Community/forum findings ---
{findings['community']}

--- Expert review findings ---
{findings['expert']}

Now synthesize ALL of this into ONE final recommendation. Respond with ONLY
valid JSON (no markdown fences, no extra text) in exactly this shape:

{{
  "summary": "one or two sentence overall summary",
  "recommendations": [
    {{
      "rank": 1,
      "name": "product or option name",
      "price": "approximate price or range",
      "pros": ["...", "..."],
      "cons": ["...", "..."],
      "community_take": "short summary of what real users/forums say",
      "expert_take": "short summary of what expert reviews say",
      "source_url": "..."
    }}
  ]
}}
"""
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=self._system_prompt(),
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        text_parts = [b.text for b in response.content if b.type == "text"]
        raw = "\n".join(text_parts).strip()
        result = _parse_json_response(raw)
        result["_raw_findings"] = findings  # kept for transparency/debugging
        return result

    # ---------- Price tracking ----------

    def check_current_price(self, search_query: str) -> dict:
        """
        Does a focused search for the current price of a specific product
        and returns a small structured result. Used by the price tracker.
        """
        prompt = f"""Search the web for the current price of: {search_query}

Respond with ONLY valid JSON (no markdown fences, no extra text) in exactly
this shape:

{{
  "price": 129.99,
  "currency": "USD",
  "source_url": "...",
  "note": "short note, e.g. if price varies by retailer or is a sale price"
}}

If you cannot find a clear current price, set "price" to null and explain
in "note".
"""
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text_parts = [b.text for b in response.content if b.type == "text"]
        raw = "\n".join(text_parts).strip()
        return _parse_json_response(raw)


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences if present and parse JSON, with a safe fallback."""
    cleaned = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "Could not parse JSON", "raw_response": raw}
