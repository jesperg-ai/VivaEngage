"""
auth.py — Gemensam MSAL-autentisering för alla scripts.

Användning:
    from auth import get_token
    token = get_token()          # Loggar in som Jesper
    token = get_token("hr")      # Loggar in som HR Agent
"""
import os
import msal
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES    = ["https://api.yammer.com/user_impersonation"]

_CACHE_FILES = {
    "jesper": "token_cache_jesper.json",
    "hr":     "token_cache_hr.json",
}

_LOGIN_HINTS = {
    "jesper": os.getenv("JESPER_EMAIL", "jesper.gunnarson@biner.se"),
    "hr":     os.getenv("HR_AGENT_EMAIL", "biner.hr.agent@biner.se"),
}


def get_token(account: str = "jesper") -> str:
    """
    Returnerar en giltig access token för angivet konto.
    Vid första anropet startas en device flow-inloggning.
    Därefter används cachad token med automatisk refresh.
    """
    cache_file = _CACHE_FILES.get(account, f"token_cache_{account}.json")
    cache = msal.SerializableTokenCache()

    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=cache
    )

    accounts = app.get_accounts()
    result = None

    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        hint = _LOGIN_HINTS.get(account, "")
        flow = app.initiate_device_flow(scopes=SCOPES, login_hint=hint or None)
        print(f"\n{'='*60}")
        print(f"  Inloggning krävs för: {hint or account}")
        print(f"  {flow['message']}")
        print(f"{'='*60}\n")
        result = app.acquire_token_by_device_flow(flow)

    if cache.has_state_changed:
        with open(cache_file, "w") as f:
            f.write(cache.serialize())

    if "access_token" in result:
        return result["access_token"]

    raise Exception(
        f"Kunde inte hämta token för '{account}': "
        f"{result.get('error_description', result.get('error'))}"
    )
