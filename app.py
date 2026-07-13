"""
Streamlit web UI for Vantage — a research & shopping assistant.

Run with:
    streamlit run app.py

Features:
- Chat interface for open-ended research
- Multi-source research mode (retail + community + expert, synthesized)
- Sidebar: view/edit remembered preferences
- Sidebar: track products and check for price drops
"""

import streamlit as st
import db
from agent import ShoppingAssistant

st.set_page_config(page_title="Vantage — Shopping Assistant", page_icon="🔶", layout="wide")

db.init_db()

# ---------- Custom styling ----------

def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3, .vantage-wordmark {
        font-family: 'Sora', sans-serif;
        letter-spacing: -0.02em;
    }

    /* Hero header */
    .vantage-hero {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 8px 0 4px 0;
    }
    .vantage-beacon {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        background: radial-gradient(circle at 30% 30%, #F6C453, #F0B429 60%, #B8790F 100%);
        box-shadow: 0 0 24px rgba(240, 180, 41, 0.55), 0 0 4px rgba(240, 180, 41, 0.8);
        flex-shrink: 0;
    }
    .vantage-wordmark {
        font-size: 32px;
        font-weight: 800;
        color: #E9EDF5;
        margin: 0;
        line-height: 1.1;
    }
    .vantage-tagline {
        color: #8B96AC;
        font-size: 15px;
        margin-top: 2px;
    }

    /* Stat chips */
    .vantage-stats {
        display: flex;
        gap: 12px;
        margin: 18px 0 8px 0;
        flex-wrap: wrap;
    }
    .vantage-stat-card {
        background: #141A29;
        border: 1px solid #262F42;
        border-radius: 12px;
        padding: 12px 18px;
        min-width: 140px;
    }
    .vantage-stat-number {
        font-family: 'Sora', sans-serif;
        font-size: 24px;
        font-weight: 700;
        color: #F0B429;
        line-height: 1.1;
    }
    .vantage-stat-label {
        color: #8B96AC;
        font-size: 12.5px;
        margin-top: 2px;
    }

    /* Recommendation / alert cards get a beacon-amber left edge */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px !important;
        border-color: #262F42 !important;
    }

    /* Buttons */
    .stButton>button {
        border-radius: 10px;
        font-weight: 500;
    }
    .stButton>button[kind="primary"] {
        background: #F0B429;
        color: #0B0F19;
        border: none;
    }
    .stButton>button[kind="primary"]:hover {
        background: #F6C453;
    }

    /* Quick-prompt chips */
    .vantage-chip-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 6px;
    }
    </style>
    """, unsafe_allow_html=True)


inject_custom_css()

# ---------- Session state ----------

if "user_id" not in st.session_state:
    st.session_state.user_id = "default"

if "assistant" not in st.session_state:
    st.session_state.assistant = ShoppingAssistant(user_id=st.session_state.user_id)

if "messages" not in st.session_state:
    st.session_state.messages = []  # for display only; agent keeps its own history

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

assistant: ShoppingAssistant = st.session_state.assistant

# ---------- Sidebar ----------

with st.sidebar:
    st.markdown("### 👤 Profile")
    new_user_id = st.text_input("User ID", value=st.session_state.user_id,
                                 help="Switch this to keep separate memory/tracked products per person.")
    if new_user_id != st.session_state.user_id:
        st.session_state.user_id = new_user_id
        st.session_state.assistant = ShoppingAssistant(user_id=new_user_id)
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("### 🧠 Remembered preferences")
    prefs = {k: v for k, v in assistant.preferences().items() if not k.startswith("_")}
    if prefs:
        for k, v in prefs.items():
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{k}**: {v}")
            if col2.button("✕", key=f"del_{k}"):
                assistant.forget(k)
                st.rerun()
    else:
        st.caption("No preferences saved yet.")

    with st.form("add_pref", clear_on_submit=True):
        pk = st.text_input("Preference name", placeholder="e.g. budget")
        pv = st.text_input("Value", placeholder="e.g. under $150")
        if st.form_submit_button("Save preference") and pk and pv:
            assistant.remember(pk, pv)
            st.rerun()

    st.divider()
    st.header("🔔 Notifications")
    st.caption("Where should price-drop alerts be sent for this user?")
    current_email = prefs.get("notify_email", "")
    current_telegram = prefs.get("notify_telegram_chat_id", "")

    with st.form("notify_settings"):
        email_val = st.text_input("Alert email", value=current_email, placeholder="you@example.com")
        telegram_val = st.text_input("Telegram chat ID", value=current_telegram,
                                      placeholder="e.g. 123456789",
                                      help="Message @userinfobot on Telegram to find your chat ID.")
        if st.form_submit_button("Save notification settings"):
            if email_val:
                assistant.remember("notify_email", email_val)
            if telegram_val:
                assistant.remember("notify_telegram_chat_id", telegram_val)
            st.success("Saved.")
            st.rerun()

    if st.button("Send test notification"):
        from notifications import notify_price_alert
        with st.spinner("Sending..."):
            results = notify_price_alert(
                st.session_state.user_id, "Test Product",
                "This is a test alert. If you got this, notifications are working!"
            )
        for n in results:
            if n["success"]:
                st.success(f"{n['channel']}: {n['detail']}")
            else:
                st.warning(f"{n['channel']}: {n['detail']}")

    st.divider()
    st.header("📉 Tracked products")
    products = db.list_tracked_products(st.session_state.user_id)

    for p in products:
        with st.expander(f"{p['name']}"):
            st.caption(f"Search: {p['search_query']}")
            if p["target_price"]:
                st.caption(f"Target price: ${p['target_price']}")
            history = db.get_price_history(p["id"])
            if history:
                st.line_chart({"price": [h["price"] for h in history if h["price"]]})
                lowest = db.get_lowest_price(p["id"])
                st.caption(f"Lowest seen so far: ${lowest}")
            else:
                st.caption("No price checks yet.")

            colA, colB = st.columns(2)
            if colA.button("Check price now", key=f"check_{p['id']}"):
                with st.spinner("Checking current price..."):
                    result = assistant.check_current_price(p["search_query"])
                    price = result.get("price")
                    if price is not None:
                        lowest_before = db.get_lowest_price(p["id"])
                        db.record_price_check(
                            p["id"], price=price,
                            source_url=result.get("source_url", ""),
                            raw_note=result.get("note", ""),
                        )
                        st.success(f"Current price: ${price}")

                        alert_msg = None
                        if p["target_price"] and price <= p["target_price"]:
                            alert_msg = f"Price ${price} is at or below your target of ${p['target_price']}!"
                        elif lowest_before and price < lowest_before:
                            alert_msg = f"New lowest price seen: ${price} (previous lowest: ${lowest_before})"

                        if alert_msg:
                            from notifications import notify_price_alert
                            notify_results = notify_price_alert(st.session_state.user_id, p["name"], alert_msg)
                            for n in notify_results:
                                if n["success"]:
                                    st.info(f"Alert sent via {n['channel']}")
                    else:
                        st.warning(result.get("note", "Couldn't find a price."))
                st.rerun()
            if colB.button("Remove", key=f"remove_{p['id']}"):
                db.remove_tracked_product(p["id"])
                st.rerun()

    with st.form("add_product", clear_on_submit=True):
        st.caption("Track a new product")
        name = st.text_input("Nickname", placeholder="e.g. Sony WH-1000XM5")
        query = st.text_input("Search query", placeholder="e.g. Sony WH-1000XM5 headphones price")
        target = st.number_input("Target price ($, optional)", min_value=0.0, step=1.0, value=0.0)
        if st.form_submit_button("Track product") and name and query:
            db.add_tracked_product(
                st.session_state.user_id, name, query,
                target_price=target if target > 0 else None,
            )
            st.rerun()

# ---------- Main area ----------

st.markdown("""
<div class="vantage-hero">
    <div class="vantage-beacon"></div>
    <div>
        <p class="vantage-wordmark">Vantage</p>
        <p class="vantage-tagline">The full view before you buy — retail, community, and expert opinion, in one place.</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Quick stats — gives returning users a sense of progress/history at a glance
_pref_count = len([k for k in assistant.preferences() if not k.startswith("_")])
_tracked = db.list_tracked_products(st.session_state.user_id)
_tracked_count = len(_tracked)
_total_checks = sum(len(db.get_price_history(p["id"])) for p in _tracked)

st.markdown(f"""
<div class="vantage-stats">
    <div class="vantage-stat-card">
        <div class="vantage-stat-number">{_tracked_count}</div>
        <div class="vantage-stat-label">Products tracked</div>
    </div>
    <div class="vantage-stat-card">
        <div class="vantage-stat-number">{_total_checks}</div>
        <div class="vantage-stat-label">Price checks logged</div>
    </div>
    <div class="vantage-stat-card">
        <div class="vantage-stat-number">{_pref_count}</div>
        <div class="vantage-stat-label">Preferences remembered</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Onboarding: auto-expanded for brand-new users (nothing tracked, no prefs,
# no chat yet), collapsed but always available afterwards, and dismissible
# so it doesn't nag returning users.
_prefs_dict = assistant.preferences()
_is_new_user = (_tracked_count == 0 and _pref_count == 0 and not st.session_state.messages)
_onboarding_dismissed = _prefs_dict.get("_onboarding_dismissed") == "true"

with st.expander("ℹ️ How Vantage works", expanded=(_is_new_user and not _onboarding_dismissed)):
    st.markdown("""
- **Chat** — ask for anything you're shopping for or researching. Vantage searches the web live and compares real options.
- **Multi-source research** — for bigger decisions, this runs three separate searches (retail prices, Reddit/forum opinion, expert reviews) and combines them into one recommendation.
- **Preferences** *(sidebar)* — save things like your budget or brand preference once, and every future answer automatically takes them into account.
- **Tracked products** *(sidebar)* — add a product you're watching, optionally with a target price. Check it anytime, or automate checks with a cron job — you'll get an email/Telegram alert on a price drop.
- **The numbers above** track your own activity here — they grow as you track products, check prices, and save preferences.
    """)
    if st.button("Got it, don't show this automatically again"):
        assistant.remember("_onboarding_dismissed", "true")
        st.rerun()

tab_chat, tab_multi = st.tabs(["💬 Chat", "🔍 Multi-source research"])

with tab_chat:
    # Quick-start prompts — only show before the first message, to lower
    # the "blank page" friction for new/returning users
    if not st.session_state.messages:
        st.caption("Try one of these, or type your own below:")
        examples = [
            "Best noise-canceling headphones under $200",
            "Compact air fryer for a small kitchen",
            "Reliable budget laptop for college",
        ]
        chip_cols = st.columns(len(examples))
        for col, example in zip(chip_cols, examples):
            if col.button(example, use_container_width=True):
                st.session_state.pending_prompt = example
                st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("What are you looking for?")
    if st.session_state.pending_prompt:
        user_input = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Searching and thinking..."):
                reply = assistant.ask(user_input)
                st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

with tab_multi:
    st.caption(
        "Runs three separate searches — retail listings, community opinion "
        "(Reddit/forums), and expert reviews — then combines them into one "
        "recommendation. Slower than regular chat, but more thorough."
    )
    goal = st.text_input("What do you want researched?", key="multi_goal",
                          placeholder="e.g. best ergonomic office chair under $400")
    run = st.button("Run multi-source research", type="primary")

    if run and goal:
        with st.spinner("Researching from multiple angles (this takes a bit longer)..."):
            result = assistant.multi_source_research(goal)

        if "error" in result:
            st.error(result["error"])
            st.code(result.get("raw_response", ""))
        else:
            st.subheader("Summary")
            st.write(result.get("summary", ""))

            for rec in result.get("recommendations", []):
                with st.container(border=True):
                    st.markdown(f"**#{rec.get('rank')} — {rec.get('name')}** · {rec.get('price')}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Pros**")
                        for pro in rec.get("pros", []):
                            st.write(f"✅ {pro}")
                    with col2:
                        st.markdown("**Cons**")
                        for con in rec.get("cons", []):
                            st.write(f"⚠️ {con}")
                    if rec.get("community_take"):
                        st.info(f"**Community says:** {rec['community_take']}")
                    if rec.get("expert_take"):
                        st.info(f"**Expert reviews say:** {rec['expert_take']}")
                    if rec.get("source_url"):
                        st.caption(f"Source: {rec['source_url']}")
    elif run and not goal:
        st.warning("Type what you'd like researched first.")
