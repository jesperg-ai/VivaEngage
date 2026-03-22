"""
monthly_stats.py
Körs automatiskt den 1:a varje månad.
Sammanställer föregående månads aktivitet på Viva Engage och postar
ett statistikinlägg i "Biner – Nyheter & Info" som Biner HR Agent.
"""
import os
import sys
import requests
from collections import defaultdict
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

# Postar som HR Agent om token finns, annars Jesper
HR_AGENT_TOKEN = os.getenv("HR_AGENT_TOKEN") or os.getenv("YAMMER_TOKEN")
HEADERS = {"Authorization": f"Bearer {HR_AGENT_TOKEN}"}
API = "https://www.yammer.com/api/v1"
TARGET_GROUP = "Nyheter"   # Matchar "Biner – Nyheter & Info"


# ---------------------------------------------------------------------------
# Datumhjälpare
# ---------------------------------------------------------------------------

def get_period(year: int = None, month: int = None):
    """Returnerar (year, month) för föregående månad om inget anges."""
    today = date.today()
    if year and month:
        return year, month
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def in_period(created_at: str, year: int, month: int) -> bool:
    """Returnerar True om created_at (ISO-sträng) tillhör angiven månad."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", ""))
        return dt.year == year and dt.month == month
    except Exception:
        return False


def after_period(created_at: str, year: int, month: int) -> bool:
    """Returnerar True om datumet är efter den angivna månaden."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", ""))
        return (dt.year, dt.month) > (year, month)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# API-anrop
# ---------------------------------------------------------------------------

def get_groups():
    resp = requests.get(f"{API}/groups.json", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_group_id(name_contains):
    groups = get_groups()
    group = next((g for g in groups if name_contains in g["full_name"]), None)
    if not group:
        raise Exception(f"Kunde inte hitta community med '{name_contains}'")
    return group["id"], group["full_name"]


def get_messages_in_period(group_id, year, month):
    """Hämtar alla meddelanden för en specifik månad från en grupp."""
    messages = []
    next_older_than = None

    while True:
        url = f"{API}/messages/in_group/{group_id}.json?threaded=false&limit=20"
        if next_older_than:
            url += f"&older_than={next_older_than}"

        resp = requests.get(url, headers=HEADERS)
        if not resp.ok:
            break
        data = resp.json()
        batch = data.get("messages", [])
        if not batch:
            break

        stop = False
        for msg in batch:
            created = msg.get("created_at", "")
            if after_period(created, year, month):
                continue          # Hoppa över framtida (sorteras nyast först)
            if in_period(created, year, month):
                messages.append(msg)
            else:
                stop = True       # Äldre än perioden – sluta hämta
                break

        if stop:
            break
        if data.get("meta", {}).get("older_available"):
            next_older_than = batch[-1]["id"]
        else:
            break

    return messages


def get_user_name(user_id, cache):
    if user_id in cache:
        return cache[user_id]
    resp = requests.get(f"{API}/users/{user_id}.json", headers=HEADERS)
    if resp.ok:
        name = resp.json().get("full_name", f"ID:{user_id}")
        cache[user_id] = name
        return name
    return f"ID:{user_id}"


# ---------------------------------------------------------------------------
# Datainsamling
# ---------------------------------------------------------------------------

def collect_data(year, month):
    """Hämtar all aktivitet för angiven månad och returnerar statistik."""
    groups = get_groups()
    print(f"  Hittade {len(groups)} communities")

    posters   = defaultdict(int)   # user_id -> antal originalinlägg
    commenters = defaultdict(int)  # user_id -> antal kommentarer
    likers    = defaultdict(int)   # namn -> antal likes givna
    user_cache = {}

    # thread_id -> {title, replies, likes}
    thread_stats = defaultdict(lambda: {"body": "", "replies": 0, "likes": 0})
    # message_id -> {body, likes}
    message_likes = {}

    for group in groups:
        msgs = get_messages_in_period(group["id"], year, month)
        print(f"    {group['full_name']}: {len(msgs)} meddelanden")

        for msg in msgs:
            sender_id  = msg.get("sender_id")
            is_reply   = msg.get("replied_to_id") is not None
            thread_id  = msg.get("thread_id")
            msg_id     = msg.get("id")
            like_count = msg.get("liked_by", {}).get("count", 0)
            body       = msg.get("body", {}).get("plain", "")[:120]

            if is_reply:
                commenters[sender_id] += 1
                if thread_id:
                    thread_stats[thread_id]["replies"] += 1
            else:
                posters[sender_id] += 1
                if thread_id:
                    thread_stats[thread_id]["body"] = body

            # Likes per meddelande
            message_likes[msg_id] = {"body": body, "likes": like_count}

            # Vem ger likes
            for liker in msg.get("liked_by", {}).get("names", []):
                likers[liker.get("full_name", "Okänd")] += 1

            # Summera likes per tråd (alla meddelanden i tråden)
            if thread_id:
                thread_stats[thread_id]["likes"] += like_count

    # Hämta namn
    all_ids = set(posters.keys()) | set(commenters.keys())
    for uid in all_ids:
        get_user_name(uid, user_cache)

    return posters, commenters, likers, user_cache, thread_stats, message_likes


# ---------------------------------------------------------------------------
# Formatering
# ---------------------------------------------------------------------------

MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


def fmt_user_toplist(data, user_cache, label, top_n=5):
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not items:
        return f"🏆 {label}\nIngen aktivitet denna månad."
    lines = [f"🏆 {label}"]
    for i, (uid, count) in enumerate(items):
        name = user_cache.get(uid, str(uid))
        unit = "inlägg" if "inlägg" in label.lower() else \
               "kommentarer" if "kommentar" in label.lower() else "likes"
        lines.append(f"{MEDALS[i]} {name} – {count} {unit}")
    return "\n".join(lines)


def fmt_name_toplist(data, label, top_n=5):
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not items:
        return f"🏆 {label}\nIngen aktivitet denna månad."
    lines = [f"🏆 {label}"]
    for i, (name, count) in enumerate(items):
        lines.append(f"{MEDALS[i]} {name} – {count} likes")
    return "\n".join(lines)


def fmt_thread_toplist(thread_stats, label, key, top_n=5):
    items = sorted(thread_stats.items(), key=lambda x: x[1][key], reverse=True)[:top_n]
    items = [(tid, s) for tid, s in items if s[key] > 0]
    if not items:
        return f"🏆 {label}\nIngen aktivitet denna månad."
    lines = [f"🏆 {label}"]
    unit = "kommentarer" if key == "replies" else "likes"
    for i, (tid, stats) in enumerate(items[:top_n]):
        count = stats[key]
        body  = stats["body"] or "(inget innehåll)"
        snippet = body[:80] + ("…" if len(body) >= 80 else "")
        lines.append(f"{MEDALS[i]} \"{snippet}\" – {count} {unit}")
    return "\n".join(lines)


def month_name_sv(month: int) -> str:
    names = ["januari","februari","mars","april","maj","juni",
             "juli","augusti","september","oktober","november","december"]
    return names[month - 1]


# ---------------------------------------------------------------------------
# Inlägg
# ---------------------------------------------------------------------------

def post_message(group_id, body):
    resp = requests.post(
        f"{API}/messages.json",
        headers=HEADERS,
        data={"body": body, "group_id": group_id}
    )
    return resp


def build_message(year, month, posters, commenters, likers,
                  user_cache, thread_stats, message_likes):
    m_name = month_name_sv(month).capitalize()

    p_list  = fmt_user_toplist(posters,    user_cache, "Flest originalinlägg", 5)
    c_list  = fmt_user_toplist(commenters, user_cache, "Flest kommentarer",    5)
    l_list  = fmt_name_toplist(likers,                 "Flest likes givna",    5)
    tr_list = fmt_thread_toplist(thread_stats, "Mest kommenterade inlägg", "replies", 5)
    tl_list = fmt_thread_toplist(thread_stats, "Mest gillade inlägg",      "likes",   5)

    return f"""📊 Viva Engage – statistik för {m_name} {year} 📊

Biner HR Agent har sammanställt förra månadens aktivitet på Viva Engage. Här är topplistorna!

{p_list}

{c_list}

{l_list}

{tr_list}

{tl_list}

Tack för er aktivitet i {m_name}! Håll engagemanget uppe 🚀
#VivaEngage #BinerInsights"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Tillåt manuellt anrop: python monthly_stats.py 2026 3
    args = sys.argv[1:]
    if len(args) == 2:
        year, month = int(args[0]), int(args[1])
    else:
        year, month = get_period()

    print(f"Sammanställer statistik för {month_name_sv(month)} {year}...")

    print("Hämtar data från Viva Engage...")
    posters, commenters, likers, user_cache, thread_stats, message_likes = \
        collect_data(year, month)

    group_id, group_name = get_group_id(TARGET_GROUP)
    print(f"Postar till: {group_name}")

    message = build_message(year, month, posters, commenters, likers,
                            user_cache, thread_stats, message_likes)

    print("\n--- Förhandsgranskning ---")
    print(message)
    print("-" * 50)

    resp = post_message(group_id, message)
    if resp.ok:
        print(f"✅ Månadsstatistik för {month_name_sv(month)} {year} postad!")
    else:
        print(f"❌ Fel: {resp.status_code} – {resp.text[:300]}")


if __name__ == "__main__":
    main()
