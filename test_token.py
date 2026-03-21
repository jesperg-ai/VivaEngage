import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("YAMMER_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
API = "https://www.yammer.com/api/v1"


def test_current_user():
    resp = requests.get(f"{API}/users/current.json", headers=HEADERS)
    print(f"Status: {resp.status_code}")
    if resp.ok:
        user = resp.json()
        print(f"Inloggad som: {user['full_name']} ({user['email']})")
        return True
    else:
        print(f"Fel: {resp.text[:200]}")
        return False


def test_groups():
    resp = requests.get(f"{API}/groups.json", headers=HEADERS)
    if resp.ok:
        groups = resp.json()
        print(f"\nAntal grupper: {len(groups)}")
        for g in groups[:5]:
            print(f"  - {g['full_name']}")
    else:
        print(f"Fel vid hämtning av grupper: {resp.status_code}")


if __name__ == "__main__":
    print("=== Testar Viva Engage API ===\n")
    if test_current_user():
        test_groups()
