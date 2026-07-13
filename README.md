# Research & Shopping Assistant (v3)

An agentic AI that researches products for you: it searches the web,
compares options across retail/community/expert sources, remembers your
preferences, tracks prices over time, and sends real email/Telegram
alerts on drops — with both a CLI and a web UI.

## What's new in this version

- 🧠 **Persistent memory** — preferences (budget, brand, must-haves) are saved
  in SQLite and automatically applied to every future research request.
- 🔍 **Multi-source research** — runs three separate searches (retail listings,
  Reddit/forum community opinion, expert reviews) and synthesizes them into
  one recommendation, rather than one generic search.
- 📉 **Price tracking + alerts** — track specific products, check their
  current price anytime, and get alerted when the price hits your target
  or a new all-time low.
- 📧 **Real notifications** — price-drop alerts are sent via email (SMTP)
  and/or Telegram, not just printed to a terminal.
- 🖥️ **Web UI** — a full Streamlit chat + dashboard interface, not just CLI.

## Deploying to the web (get a real link)

This app is ready to deploy to [Streamlit Community Cloud](https://share.streamlit.io)
for free, which gives you a real URL like `https://yourname-shopping-assistant.streamlit.app`
that works from any browser, on any device.

1. **Push this code to a GitHub repo.**
   Do NOT commit your real `.env` or `.streamlit/secrets.toml` — the
   included `.gitignore` already excludes both.

2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.

3. **Click "New app"**, select your repo, and set the main file to `app.py`.

4. **Add your secrets.** In the app's "Settings → Secrets" box, paste the
   contents of `.streamlit/secrets.toml.example` (filled in with your real
   values). This is the cloud equivalent of your local `.env` file — the
   app automatically reads from here instead when deployed, thanks to
   `config.py`.

5. **Click Deploy.** After a minute or two you'll get your live link.

The same codebase works identically whether you run it locally (reading
from `.env`) or deployed on Streamlit Cloud (reading from its Secrets
manager) — `config.py` handles picking the right source automatically.

## Setup (local use)

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your API key + notification settings
```

### Notification setup (optional but recommended)

**Email** — works with Gmail or any SMTP provider:
1. If using Gmail, create an ["app password"](https://myaccount.google.com/apppasswords)
   (your regular password won't work with 2FA enabled).
2. Fill in `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` in `.env`.

**Telegram**:
1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`,
   follow the prompts — it gives you a bot token.
2. Message your new bot at least once (so it's allowed to message you back).
3. Message [@userinfobot](https://t.me/userinfobot) to get your numeric chat ID.
4. Fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.

These are global defaults. Each user can also override where *their* alerts
go (useful if multiple people share one deployment — e.g. hostel-mates)
via the CLI's `notify` command or the Streamlit sidebar, without touching
`.env` at all.

## Usage

### Option A: Web UI (recommended)

```bash
streamlit run app.py
```

This gives you:
- A chat tab for normal research conversations
- A "Multi-source research" tab for deeper comparisons
- A sidebar to view/edit remembered preferences
- A sidebar to configure notification email/Telegram + send a test alert
- A sidebar to track products, see price history charts, and check prices on demand

### Option B: Command line

```bash
python cli.py [user_id]
```

Commands available inside the CLI:
```
remember <key>=<value>     save a preference, e.g. remember budget=under $150
forget <key>                remove a saved preference
prefs                        show saved preferences
notify email=<addr>          set your alert email
notify telegram=<chat_id>    set your alert Telegram chat id
testnotify                   send a test alert to your configured channels
track <name> | <query> | <target price>
                              e.g. track Sony XM5 | Sony WH-1000XM5 price | 250
tracked                      list tracked products
checkprices                  check current prices for all tracked products
                              (sends notifications for any alerts triggered)
multi <goal>                 run multi-source research (retail+community+expert)
reset                        start a fresh chat session
quit / exit                  leave
```

Anything else you type is treated as a normal research question.

### Automating price checks

`price_tracker.py` can be run standalone (e.g. from a daily cron job) and
will send real notifications for any alerts:

```bash
python price_tracker.py alice
```

Example crontab entry to run it every morning at 9am:
```
0 9 * * * cd /path/to/shopping_assistant && python3 price_tracker.py alice
```

## Files

- `agent.py` — core agent: chat, structured output, multi-source research,
  memory-aware prompts, single-product price checks
- `config.py` — reads settings from Streamlit secrets (cloud) or .env (local)
- `db.py` — SQLite persistence: preferences + tracked products + price history
- `notifications.py` — sends email (SMTP) and/or Telegram alerts, with
  per-user channel overrides via preferences
- `price_tracker.py` — checks all tracked products, detects price drops/target
  hits, and triggers notifications
- `app.py` — Streamlit web UI (chat + multi-source tab + sidebar dashboard)
- `cli.py` — command-line interface with all the same features
- `example_structured.py` — minimal example of one-shot structured JSON output
- `requirements.txt` — Python dependencies
- `.env.example` — template for local use (API key + notification settings)
- `.streamlit/secrets.toml.example` — template for Streamlit Cloud deployment
- `.gitignore` — keeps your real `.env`/`secrets.toml`/database out of GitHub

## How the pieces fit together

```
                     ┌─────────────┐
                     │   db.py     │  preferences, tracked products,
                     │  (SQLite)   │  price history
                     └──────┬──────┘
                            │ read/write
                            ▼
   ┌──────────┐      ┌─────────────┐      ┌──────────────────┐
   │ cli.py   │─────▶│  agent.py   │◀─────│     app.py        │
   │ app.py   │      │ (Claude +   │      │  (Streamlit UI)   │
   └──────────┘      │ web search) │      └──────────────────┘
                      └──────┬──────┘
                            │
                            ▼
                     ┌──────────────┐      ┌────────────────────┐
                     │price_tracker │─────▶│  notifications.py   │
                     │    .py       │      │  (email/Telegram)   │
                     └──────────────┘      └────────────────────┘
```

## Notes / things worth knowing

- Model used: `claude-sonnet-5` (set in `agent.py`, `MODEL` constant).
- Multi-source research makes 4 API calls per request (3 searches + 1
  synthesis), so it's slower and more expensive per query than regular
  chat — use it when you want real thoroughness, not for quick questions.
- The SQLite file `assistant.db` is created automatically on first run in
  whatever directory you run the app/CLI from.
- `user_id` is just a string you choose — use different ones to keep
  separate memory/tracked products/notification settings per person.
- If email or Telegram aren't configured, `notifications.py` fails
  gracefully (returns a clear "not configured" message) instead of
  crashing — so you can leave one or both unset with no issues.

## Ideas for what's next

- **Scheduling**: instead of manually running `price_tracker.py`, wire it
  up to a proper scheduler (cron, or a Python `schedule`-based loop) so
  checks happen automatically.
- **Guardrails for real purchases**: if you ever let the agent actually
  add-to-cart or buy something, always require an explicit human
  confirmation step before any purchase action.
- **Preference auto-extraction**: instead of only explicit `remember`
  commands, have Claude detect stated preferences mid-conversation
  ("I always prefer wireless") and offer to save them automatically.
- **Multi-channel digest**: instead of one notification per alert, batch
  a daily summary of all price changes into a single message.

