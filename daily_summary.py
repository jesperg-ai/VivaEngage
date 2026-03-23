"""
Viva Engage – Dagssammanfattning
Returnerar en textsträng redo att klistras in i Coworks dagliga rapport.
Kör: python daily_summary.py
"""
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
sys.path.insert(0, r"C:\Users\JesperGunnarson\Projects\VivaEngage")
from auth import get_token

BASE_URL = "https://www.yammer.com/api/v1"
MY_USER = "jesper.gunnarson@biner.se"  # Används för att filtrera egna inlägg


def get_headers():
    token = get_token("jesper")
    return {"Authorization": f"Bearer {token}"}


def is_today(date_str):
    """Returnerar True om datumet är från de senaste 24 timmarna."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        return dt >= cutoff
    except Exception:
        return False


def fetch(endpoint, headers, params=None):
    url = f"{BASE_URL}{endpoint}"
    r = requests.get(url, headers=headers, params=params or {})
    r.raise_for_status()
    return r.json()


def format_message(msg):
    """Returnerar en kort rad med avsändare + ämne/innehåll."""
    sender = msg.get("sender_name") or msg.get("sender", {}).get("full_name", "Okänd")
    body = msg.get("body", {}).get("plain", "").strip()
    body = body[:120] + "…" if len(body) > 120 else body
    group = msg.get("group_name") or ""
    group_str = f" [{group}]" if group else ""
    return f"- **{sender}**{group_str}: {body}"


def main():
    headers = get_headers()
    lines = []

    # ── 1. @mentions och inbox ──────────────────────────────────────────────
    try:
        inbox = fetch("/messages/inbox.json", headers)
        messages = inbox.get("messages", [])
        mentions = [m for m in messages if is_today(m.get("created_at", ""))]
        if mentions:
            lines.append(f"**@Mentions och svar ({len(mentions)})**")
            for m in mentions[:5]:
                lines.append(format_message(m))
        else:
            lines.append("*Inga @mentions eller svar sedan igår.*")
    except Exception as e:
        lines.append(f"*Kunde inte hämta inbox: {e}*")

    lines.append("")

    # ── 2. Nya inlägg i min feed ────────────────────────────────────────────
    try:
        feed = fetch("/messages/my_feed.json", headers)
        messages = feed.get("messages", [])
        new_posts = [
            m for m in messages
            if is_today(m.get("created_at", ""))
            and m.get("sender_email", "").lower() != MY_USER.lower()
        ]
        if new_posts:
            lines.append(f"**Nya inlägg i mina communities ({len(new_posts)})**")
            for m in new_posts[:5]:
                lines.append(format_message(m))
        else:
            lines.append("*Inga nya inlägg i din feed sedan igår.*")
    except Exception as e:
        lines.append(f"*Kunde inte hämta feed: {e}*")

    lines.append("")

    # ── 3. Olästa notifikationer ────────────────────────────────────────────
    try:
        notif_data = fetch("/notifications.json", headers)
        notifs = notif_data.get("notifications", [])
        unread = [n for n in notifs if not n.get("read")]
        if unread:
            lines.append(f"**Olästa notifikationer: {len(unread)}**")
            for n in unread[:3]:
                lines.append(f"- {n.get('body', 'Ingen detalj')}")
        else:
            lines.append("*Inga olästa notifikationer.*")
    except Exception as e:
        lines.append(f"*Kunde inte hämta notifikationer: {e}*")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
