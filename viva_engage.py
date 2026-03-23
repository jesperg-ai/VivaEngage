import requests
from auth import get_token

YAMMER_API = "https://www.yammer.com/api/v1"


def get_current_user(token):
    resp = requests.get(
        f"{YAMMER_API}/users/current.json",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()


def get_groups(token):
    resp = requests.get(
        f"{YAMMER_API}/groups.json",
        headers={"Authorization": f"Bearer {token}"}
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    token = get_token("jesper")
    print("Inloggad!\n")

    user = get_current_user(token)
    print(f"Användare: {user['full_name']} ({user['email']})")

    print("\nGrupper du tillhör:")
    groups = get_groups(token)
    for g in groups:
        print(f"  - {g['full_name']}")
