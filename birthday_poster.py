"""
birthday_poster.py
Körs dagligen. Hämtar aktiva medarbetare från Simployer,
hittar de som fyller år idag och postar gratulationer på Viva Engage.
"""
import os
import random
import hashlib
import requests
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

SIMPLOYER_TOKEN = os.getenv("SIMPLOYER_TOKEN")
YAMMER_TOKEN = os.getenv("YAMMER_TOKEN")

SIMPLOYER_API = "https://api.alexishr.com/v1"
YAMMER_API = "https://www.yammer.com/api/v1"
TARGET_GROUP = "Kultur"  # Matchar "Biner – Kultur & Gemenskap"


def get_active_employees():
    headers = {"Authorization": f"Bearer {SIMPLOYER_TOKEN}"}
    all_employees = []
    offset = 0
    while True:
        resp = requests.get(
            f"{SIMPLOYER_API}/employee",
            headers=headers,
            params={"limit": 100, "offset": offset}
        )
        resp.raise_for_status()
        data = resp.json()
        all_employees.extend(data.get("data", []))
        if len(all_employees) >= data.get("total", 0):
            break
        offset += 100
    return [e for e in all_employees if e.get("active") is True]


def get_todays_birthdays(employees):
    today = date.today()
    birthdays = []
    for e in employees:
        bd_str = e.get("birthDate")
        if not bd_str:
            continue
        bd = datetime.fromisoformat(bd_str.replace("Z", "")).date()
        if bd.month == today.month and bd.day == today.day:
            age = today.year - bd.year
            first_name = e.get("firstName", "").strip()
            last_name = e.get("lastName", "").strip()
            birthdays.append({
                "name": f"{first_name} {last_name}",
                "first_name": first_name,
                "age": age,
            })
    return birthdays


def get_group_id(group_name_contains):
    headers = {"Authorization": f"Bearer {YAMMER_TOKEN}"}
    resp = requests.get(f"{YAMMER_API}/groups.json", headers=headers)
    resp.raise_for_status()
    groups = resp.json()
    group = next((g for g in groups if group_name_contains in g["full_name"]), None)
    if not group:
        raise Exception(f"Kunde inte hitta community med '{group_name_contains}'")
    return group["id"], group["full_name"]


TEMPLATES = [
    lambda name, first, age: (
        f"🎂 Grattis {name} på {age}-årsdagen! 🎉\n\n"
        f"Idag fyller {first} {age} år – vi önskar dig en riktigt grym födelsedag! 🥳🎈"
    ),
    lambda name, first, age: (
        f"🎉 Idag är det {first}s stora dag!\n\n"
        f"{name} fyller {age} år – stort grattis från oss alla på Biner! 🎂✨"
    ),
    lambda name, first, age: (
        f"🥳 {age} år – vilket jubileum!\n\n"
        f"Vi hälsar {name} en riktigt härlig födelsedag! "
        f"Hoppas dagen bjuder på massor av skratt och firande 🎈🎊"
    ),
    lambda name, first, age: (
        f"🎈 Födelsedagshälsning till {name}!\n\n"
        f"Idag den {date.today().strftime('%-d %B')} fyller {first} {age} år. "
        f"Grattis – du är ovärderlig för Biner! 💪🎂"
    ),
    lambda name, first, age: (
        f"🌟 Idag firar vi {first}!\n\n"
        f"{name} fyller {age} år idag. "
        f"Tack för allt du bidrar med – ha en fantastisk födelsedag! 🎉🥂"
    ),
    lambda name, first, age: (
        f"🎊 Grattis på dagen, {first}! 🎊\n\n"
        f"Hela Biner önskar {name} en strålande {age}-årsdag! "
        f"Må det bli en dag att minnas 🎂🎈"
    ),
    lambda name, first, age: (
        f"🥂 {name} – idag är din dag!\n\n"
        f"Vi hoppas att ditt {age}:e år blir ditt bästa hittills. "
        f"Grattis på födelsedagen från oss alla! 🎉🌟"
    ),
]


def pick_template(name):
    """Väljer mall deterministiskt baserat på namn + år, så samma person
    inte får samma text två år i rad."""
    seed = int(hashlib.md5(f"{name}{date.today().year}".encode()).hexdigest(), 16)
    return TEMPLATES[seed % len(TEMPLATES)]


def post_birthday(group_id, person):
    headers = {"Authorization": f"Bearer {YAMMER_TOKEN}"}
    name = person["name"]
    age = person["age"]
    first_name = person["first_name"]

    template = pick_template(name)
    message = template(name, first_name, age)

    resp = requests.post(
        f"{YAMMER_API}/messages.json",
        headers=headers,
        data={"body": message, "group_id": group_id}
    )
    return resp


def main():
    today = date.today()
    print(f"Kör födelsedagsskript för {today.strftime('%d %B %Y')}")

    print("Hämtar medarbetare från Simployer...")
    employees = get_active_employees()
    print(f"  {len(employees)} aktiva medarbetare hittade")

    birthdays = get_todays_birthdays(employees)

    if not birthdays:
        print("Inga födelsedagar idag.")
        return

    print(f"\n{len(birthdays)} fyller år idag:")
    for p in birthdays:
        print(f"  - {p['name']} ({p['age']} år)")

    group_id, group_name = get_group_id(TARGET_GROUP)
    print(f"\nPostar till: {group_name}")

    for person in birthdays:
        resp = post_birthday(group_id, person)
        if resp.ok:
            print(f"  ✅ Postat gratulation för {person['name']}")
        else:
            print(f"  ❌ Fel för {person['name']}: {resp.status_code} – {resp.text[:200]}")


if __name__ == "__main__":
    main()
