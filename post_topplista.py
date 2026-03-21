import os
import requests
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YAMMER_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
API = "https://www.yammer.com/api/v1"


def get_groups():
    resp = requests.get(f"{API}/groups.json", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_messages_in_group(group_id):
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
            if created.startswith("2026"):
                messages.append(msg)
            elif created < "2026":
                stop = True
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


def collect_data(groups):
    posts = defaultdict(int)
    comments = defaultdict(int)
    likes = defaultdict(int)
    user_cache = {}

    for group in groups:
        messages = get_messages_in_group(group["id"])
        for msg in messages:
            sender_id = msg.get("sender_id")
            is_reply = msg.get("replied_to_id") is not None
            if is_reply:
                comments[sender_id] += 1
            else:
                posts[sender_id] += 1
            for liker in msg.get("liked_by", {}).get("names", []):
                name = liker.get("full_name", "Okänd")
                likes[name] += 1

    all_ids = set(posts.keys()) | set(comments.keys())
    for uid in all_ids:
        get_user_name(uid, user_cache)

    return posts, comments, likes, user_cache


def format_toplist(data_dict, user_cache, label, top_n=5):
    sorted_items = sorted(data_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]
    lines = [f"🏆 Topplista – {label}"]
    for i, (uid, count) in enumerate(sorted_items, 1):
        name = user_cache.get(uid, uid) if isinstance(uid, int) else uid
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
        lines.append(f"{medal} {name} – {count}")
    return "\n".join(lines)


def format_likes_toplist(likes_dict, top_n=5):
    sorted_items = sorted(likes_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]
    lines = ["🏆 Topplista – Flest likes givna"]
    for i, (name, count) in enumerate(sorted_items, 1):
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
        lines.append(f"{medal} {name} – {count}")
    return "\n".join(lines)


def post_message(group_id, body):
    resp = requests.post(
        f"{API}/messages.json",
        headers=HEADERS,
        data={"body": body, "group_id": group_id}
    )
    return resp


def main():
    print("Hämtar data...")
    groups = get_groups()

    target_group = next((g for g in groups if "Nyheter" in g["full_name"]), None)
    if not target_group:
        print("Kunde inte hitta Biner – Nyheter & Info!")
        return

    group_id = target_group["id"]
    print(f"Postar till: {target_group['full_name']} (ID: {group_id})")

    posts, comments, likes, user_cache = collect_data(groups)

    posts_list = format_toplist(posts, user_cache, "Flest inlägg")
    comments_list = format_toplist(comments, user_cache, "Flest kommentarer")
    likes_list = format_likes_toplist(likes)

    message = f"""🎯 Viva Engage topplista 2026 – till vårdagjämningen 🌸

Jag testar Vibe Coding – min kod hämtar data via API, sammanställer statistiken och postar detta inlägg helt automatiskt! 🤖✨

💻 Jesper vibe codar – och låter AI:n göra jobbet!

Här är årets topplista så här långt:

{posts_list}

{comments_list}

{likes_list}

Håll er aktiva på Viva Engage – nästa uppdatering kanske just du toppar listan! 🚀"""

    print("\nFörhandsgranskning av inlägg:")
    print("-" * 50)
    print(message)
    print("-" * 50)

    confirm = input("\nVill du posta detta? (ja/nej): ").strip().lower()
    if confirm != "ja":
        print("Avbrutet.")
        return

    resp = post_message(group_id, message)
    if resp.ok:
        print("✅ Inlägget är postat!")
    else:
        print(f"❌ Fel: {resp.status_code} – {resp.text[:300]}")


if __name__ == "__main__":
    main()
