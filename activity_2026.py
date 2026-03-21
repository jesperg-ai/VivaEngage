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


def get_messages_in_group(group_id, group_name):
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


def get_liked_by(message_id):
    resp = requests.get(f"{API}/messages/{message_id}/liked_by.json", headers=HEADERS)
    if resp.ok:
        data = resp.json()
        return data.get("names", [])
    return []


def get_user_name(user_id, cache):
    if user_id in cache:
        return cache[user_id]
    resp = requests.get(f"{API}/users/{user_id}.json", headers=HEADERS)
    if resp.ok:
        name = resp.json().get("full_name", f"ID:{user_id}")
        cache[user_id] = name
        return name
    return f"ID:{user_id}"


def main():
    print("Hämtar grupper...")
    groups = get_groups()
    print(f"Hittade {len(groups)} grupper\n")

    posts = defaultdict(lambda: defaultdict(int))       # user_id -> community -> antal poster
    comments = defaultdict(lambda: defaultdict(int))    # user_id -> community -> antal kommentarer
    likes = defaultdict(int)                            # "Namn" -> antal likes
    user_cache = {}
    all_messages = []

    for group in groups:
        group_name = group["full_name"]
        group_id = group["id"]
        print(f"Hämtar inlägg från: {group_name}...")
        messages = get_messages_in_group(group_id, group_name)

        for msg in messages:
            sender_id = msg.get("sender_id")
            is_reply = msg.get("replied_to_id") is not None

            if is_reply:
                comments[sender_id][group_name] += 1
            else:
                posts[sender_id][group_name] += 1

            all_messages.append((msg, group_name))

    # Likes finns inbakade i varje meddelande
    for msg, group_name in all_messages:
        for liker in msg.get("liked_by", {}).get("names", []):
            name = liker.get("full_name", "Okänd")
            likes[name] += 1

    # Hämta namn för poster och kommentarer
    all_user_ids = set(posts.keys()) | set(comments.keys())
    for uid in all_user_ids:
        get_user_name(uid, user_cache)

    def print_section(title, data):
        print(f"\n{'='*60}")
        print(title)
        print("="*60)
        totals = {uid: sum(communities.values()) for uid, communities in data.items()}
        for uid, total in sorted(totals.items(), key=lambda x: x[1], reverse=True):
            name = user_cache.get(uid, f"ID:{uid}")
            print(f"\n{name} — {total} totalt")
            for community, count in sorted(data[uid].items(), key=lambda x: x[1], reverse=True):
                print(f"    {count:3d}  {community}")
        print(f"\nTotalt: {sum(totals.values())} från {len(totals)} användare")

    print_section("POSTER 2026 (originalinlägg)", posts)
    print_section("KOMMENTARER 2026", comments)

    print(f"\n{'='*60}")
    print("LIKES 2026 (vem ger mest likes)")
    print("="*60)
    for name, count in sorted(likes.items(), key=lambda x: x[1], reverse=True):
        print(f"  {count:3d}  {name}")
    print(f"\nTotalt: {sum(likes.values())} likes från {len(likes)} användare")


if __name__ == "__main__":
    main()
