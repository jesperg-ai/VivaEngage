import os
import json
import requests
import msal
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://api.yammer.com/user_impersonation"]
CACHE_FILE = "token_cache.json"
YAMMER_API = "https://www.yammer.com/api/v1"


def get_token():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        cache.deserialize(open(CACHE_FILE).read())

    app = msal.PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=cache
    )

    accounts = app.get_accounts()
    result = None

    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        print(flow["message"])  # Visar länk + kod för inloggning
        result = app.acquire_token_by_device_flow(flow)

    if cache.has_state_changed:
        open(CACHE_FILE, "w").write(cache.serialize())

    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Kunde inte hämta token: {result.get('error_description')}")


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
    token = get_token()
    print("Inloggad!\n")

    user = get_current_user(token)
    print(f"Användare: {user['full_name']} ({user['email']})")

    print("\nGrupper du tillhör:")
    groups = get_groups(token)
    for g in groups:
        print(f"  - {g['full_name']}")
