"""
post_topplista.py
Körs automatiskt kl 08:00 på första arbetsdagen varje månad.
Hämtar statistik för föregående månad och postar topplista i Biner – Nyheter & Info.
"""
import requests
from collections import defaultdict
from datetime import date, timedelta
from auth import get_token
from timereport_reminder import swedish_holidays

API = "https://www.yammer.com/api/v1"

MONTH_NAMES = [
    "", "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december"
]


# ---------------------------------------------------------------------------
# Datumlogik
# ---------------------------------------------------------------------------

def previous_month(today: date) -> tuple[int, int]:
    """Returnerar (år, månad) för föregående månad."""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def first_working_day(year: int, month: int) -> date:
    """Returnerar första arbetsdagen (mån–fre, ej helgdag) i angiven månad."""
    d = date(year, month, 1)
    holidays = swedish_holidays(year)
    while d.weekday() >= 5 or d in holidays:
        d += timedelta(days=1)
    return d


def is_first_working_day_today() -> bool:
    today = date.today()
    fwd = first_working_day(today.year, today.month)
    return today == fwd


# ---------------------------------------------------------------------------
# API-hjälpare
# ---------------------------------------------------------------------------

def get_groups(headers):
    resp = requests.get(f"{API}/groups.json", headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_messages_in_group(headers, group_id, year_str, month_str):
    """Hämtar alla meddelanden i en grupp för en specifik månad (YYYY-MM)."""
    messages = []
    next_older_than = None
    prefix = f"{year_str}-{month_str}"

    while True:
        url = f"{API}/messages/in_group/{group_id}.json?threaded=false&limit=20"
        if next_older_than:
            url += f"&older_than={next_older_than}"
        resp = requests.get(url, headers=headers)
        if not resp.ok:
            break
        data = resp.json()
        batch = data.get("messages", [])
        if not batch:
            break

        stop = False
        for msg in batch:
            created = msg.get("created_at", "")
            if created.startswith(prefix):
                messages.append(msg)
            elif created < prefix:
                stop = True
                break

        if stop:
            break
        if data.get("meta", {}).get("older_available"):
            next_older_than = batch[-1]["id"]
        else:
            break

    return messages


def get_user_name(headers, user_id, cache):
    if user_id in cache:
        return cache[user_id]
    resp = requests.get(f"{API}/users/{user_id}.json", headers=headers)
    if resp.ok:
        name = resp.json().get("full_name", f"ID:{user_id}")
        cache[user_id] = name
        return name
    return f"ID:{user_id}"


# ---------------------------------------------------------------------------
# Datainsamling
# ---------------------------------------------------------------------------

def collect_data(headers, groups, year_str, month_str):
    posts       = defaultdict(int)   # sender_id -> antal
    comments    = defaultdict(int)   # sender_id -> antal
    likes_given = defaultdict(int)   # "Namn" -> antal likes givna
    msg_comments = defaultdict(int)  # (msg_id, body_snippet) -> antal kommentarer
    msg_likes    = defaultdict(int)  # (msg_id, body_snippet) -> antal likes
    user_cache  = {}
    thread_map  = {}                 # thread_id -> body_snippet

    all_messages = []

    for group in groups:
        msgs = get_messages_in_group(headers, group["id"], year_str, month_str)
        for msg in msgs:
            sender_id = msg.get("sender_id")
            thread_id = msg.get("thread_id")
            msg_id    = msg.get("id")
            body      = msg.get("body", {}).get("plain", "")[:60].strip()
            is_reply  = msg.get("replied_to_id") is not None

            if is_reply:
                comments[sender_id] += 1
                if thread_id in thread_map:
                    msg_comments[thread_id] += 1
            else:
                posts[sender_id] += 1
                thread_map[thread_id] = body

            for liker in msg.get("liked_by", {}).get("names", []):
                name = liker.get("full_name", "Okänd")
                likes_given[name] += 1
                msg_likes[(msg_id, body)] += 1

            all_messages.append(msg)

    for uid in set(posts.keys()) | set(comments.keys()):
        get_user_name(headers, uid, user_cache)

    return posts, comments, likes_given, msg_comments, msg_likes, user_cache, thread_map


# ---------------------------------------------------------------------------
# Formatering
# ---------------------------------------------------------------------------

def fmt_user_toplist(data, user_cache, label, top_n=5):
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:top_n]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = [f"📊 Flest {label}"]
    for i, (uid, count) in enumerate(items):
        name = user_cache.get(uid, f"ID:{uid}")
        lines.append(f"{medals[i]} {name} – {count}")
    return "\n".join(lines)


def fmt_likes_toplist(likes_given, top_n=5):
    items = sorted(likes_given.items(), key=lambda x: x[1], reverse=True)[:top_n]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = ["👍 Flest likes givna"]
    for i, (name, count) in enumerate(items):
        lines.append(f"{medals[i]} {name} – {count}")
    return "\n".join(lines)


def fmt_top_posts(msg_comments, thread_map, top_n=3):
    items = sorted(msg_comments.items(), key=lambda x: x[1], reverse=True)[:top_n]
    medals = ["🥇", "🥈", "🥉"]
    lines = ["💬 Mest kommenterade inlägg"]
    for i, (thread_id, count) in enumerate(items):
        snippet = thread_map.get(thread_id, "...")[:50]
        lines.append(f"{medals[i]} \"{snippet}...\" – {count} kommentarer")
    return "\n".join(lines)


def fmt_top_liked_posts(msg_likes, top_n=3):
    items = sorted(msg_likes.items(), key=lambda x: x[1], reverse=True)[:top_n]
    medals = ["🥇", "🥈", "🥉"]
    lines = ["❤️ Mest gillade inlägg"]
    for i, ((msg_id, body), count) in enumerate(items):
        snippet = body[:50]
        lines.append(f"{medals[i]} \"{snippet}...\" – {count} likes")
    return "\n".join(lines)


def post_message(headers, group_id, body):
    resp = requests.post(
        f"{API}/messages.json",
        headers=headers,
        data={"body": body, "group_id": group_id}
    )
    return resp


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    today = date.today()

    if not is_first_working_day_today():
        fwd = first_working_day(today.year, today.month)
        print(f"Idag ({today}) är inte första arbetsdagen i månaden (det är {fwd}).")
        print("Inget inlägg postas.")
        return

    prev_year, prev_month = previous_month(today)
    year_str  = str(prev_year)
    month_str = f"{prev_month:02d}"
    month_name = MONTH_NAMES[prev_month]

    print(f"✅ Första arbetsdagen i {MONTH_NAMES[today.month]} – hämtar data för {month_name} {prev_year}...")

    token   = get_token("jesper")
    headers = {"Authorization": f"Bearer {token}"}

    groups = get_groups(headers)
    target = next((g for g in groups if "Nyheter" in g["full_name"]), None)
    if not target:
        print("❌ Kunde inte hitta Biner – Nyheter & Info!")
        return

    posts, comments, likes_given, msg_comments, msg_likes, user_cache, thread_map = \
        collect_data(headers, groups, year_str, month_str)

    posts_list    = fmt_user_toplist(posts, user_cache, "inlägg", 5)
    comments_list = fmt_user_toplist(comments, user_cache, "kommentarer", 5)
    likes_list    = fmt_likes_toplist(likes_given, 5)
    top_posts     = fmt_top_posts(msg_comments, thread_map, 3)
    top_liked     = fmt_top_liked_posts(msg_likes, 3)

    message = f"""📅 Viva Engage – Topplista för {month_name} {prev_year}

Här kommer månadens sammanställning av aktiviteten på Viva Engage! 🚀

{posts_list}

{comments_list}

{likes_list}

{top_posts}

{top_liked}

Tack för att ni håller Viva Engage levande! 💪 Fortsätt dela, kommentera och engagera er – vi ses i flödet! 🎯"""

    print("\n--- Förhandsgranskning ---")
    print(message)
    print("-" * 50)

    resp = post_message(headers, target["id"], message)
    if resp.ok:
        print(f"✅ Topplista för {month_name} {prev_year} postad!")
    else:
        print(f"❌ Fel: {resp.status_code} – {resp.text[:300]}")


if __name__ == "__main__":
    main()
