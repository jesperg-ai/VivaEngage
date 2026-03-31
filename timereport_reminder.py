"""
timereport_reminder.py
Körs automatiskt på sista arbetsdagen varje månad.
Postar en påminnelse om tidrapportering i "Biner – Nyheter & Info" som Jesper.
Taggar Henrik och Annelie.
"""
import os
import requests
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from auth import get_token

load_dotenv()

HENRIK_ID       = os.getenv("HENRIK_USER_ID", "1575197266")
ANNELIE_ID      = os.getenv("ANNELIE_USER_ID", "6401258684416")
API             = "https://www.yammer.com/api/v1"
TARGET_GROUP    = "Nyheter"   # Matchar "Biner – Nyheter & Info"
POSTED_MARKER   = Path(__file__).parent / ".timereport_posted"


# ---------------------------------------------------------------------------
# Svenska helgdagar (rörliga beräknas, fasta hårdkodade)
# ---------------------------------------------------------------------------

def swedish_holidays(year: int) -> set:
    """Returnerar ett set av date-objekt för svenska helgdagar."""

    def easter(y):
        """Beräknar påskdagen (Gregorisk)."""
        a = y % 19
        b, c = divmod(y, 100)
        d, e = divmod(b, 4)
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i, k = divmod(c, 4)
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month, day = divmod(114 + h + l - 7 * m, 31)
        return date(y, month, day + 1)

    e = easter(year)
    holidays = {
        # Fasta
        date(year, 1, 1),   # Nyårsdagen
        date(year, 1, 6),   # Trettondedag jul
        date(year, 5, 1),   # Första maj
        date(year, 6, 6),   # Nationaldagen
        date(year, 12, 24), # Julafton (de flesta lediga)
        date(year, 12, 25), # Juldagen
        date(year, 12, 26), # Annandag jul
        date(year, 12, 31), # Nyårsafton
        # Rörliga
        e - timedelta(days=2),   # Långfredag
        e,                       # Påskdagen
        e + timedelta(days=1),   # Annandag påsk
        e + timedelta(days=39),  # Kristi himmelsfärd
        e + timedelta(days=49),  # Pingstdagen
    }
    # Midsommarafton = fredagen mellan 19-25 juni
    midsommar_eve = date(year, 6, 19)
    while midsommar_eve.weekday() != 4:   # 4 = fredag
        midsommar_eve += timedelta(days=1)
    holidays.add(midsommar_eve)
    holidays.add(midsommar_eve + timedelta(days=1))  # Midsommardagen

    # Alla helgons dag = lördagen 31 okt – 6 nov
    alla_helgon = date(year, 10, 31)
    while alla_helgon.weekday() != 5:   # 5 = lördag
        alla_helgon += timedelta(days=1)
    holidays.add(alla_helgon)

    return holidays


def last_working_day(year: int, month: int) -> date:
    """Returnerar sista arbetsdagen (mån–fre, ej helgdag) i angiven månad."""
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)

    holidays = swedish_holidays(year)
    while last.weekday() >= 5 or last in holidays:   # 5=lör, 6=sön
        last -= timedelta(days=1)
    return last


def is_last_working_day_today() -> bool:
    today = date.today()
    lwd = last_working_day(today.year, today.month)
    return today == lwd


# ---------------------------------------------------------------------------
# Månadsspecifika intro-variationer (en per månad)
# ---------------------------------------------------------------------------

MONTH_INTROS = {
    1:  (
        "🥂 Nytt år, samma rutiner!",
        "Hoppas 1 januari var vilsam – för nu är det dags att komma igång på riktigt. "
        "Januari är slut och tidrapporten väntar."
    ),
    2:  (
        "📅 Sista arbetsdagen i februari",
        "I slutet av 1920-talet experimenterade Sovjet­unionen med kalendern och hade "
        "både 29:e och 30:e februari vissa år.\n\nDen ursäkten fungerar tyvärr inte hos oss. "
        "Februari har det antal dagar den har – och idag är sista arbetsdagen."
    ),
    3:  (
        "🌱 Mars är slut – våren börjar, månaden stängs",
        "Världens äldsta kända kalender räknade bara tio månader och mars var faktiskt "
        "månad nummer ett.\n\nHos oss räknar vi tolv – och den tredje stänger nu."
    ),
    4:  (
        "☀️ April är slut – ingen aprilskämt den här gången",
        "April har 30 dagar, och alla 30 behöver vara tidrapporterade. "
        "Det är inget skämt."
    ),
    5:  (
        "🌸 Maj säger hej då",
        "Maj har historiskt sett varit månaden för firande, valborg och ledighet. "
        "Men innan du avslutar semesterkänslorna – tidrapporten ska stängas."
    ),
    6:  (
        "☀️ Juni – midsommar är förbi, månaden likaså",
        "Midsommar är en av Sveriges mest älskade traditioner. "
        "Men den räknas inte som ursäkt för sen tidrapport. "
        "Juni stänger idag."
    ),
    7:  (
        "🏖️ Juli – semestern börjar men månaden slutar",
        "Många är på semester, men tidrapporten tar inte semester. "
        "Se till att juli är stängd och klar innan du slappnar av helt."
    ),
    8:  (
        "🍂 Augusti – sommaren tar slut, rutinerna är tillbaka",
        "Statistik visar att produktiviteten ökar markant i september. "
        "Starta den uppgången rätt – med en stängd augustirapport."
    ),
    9:  (
        "🍁 September – hösten är här och månaden stänger",
        "Begreppet 'deadline' sägs komma från fängelsernas tid på 1800-talet – "
        "en linje man inte fick passera.\n\nVår deadline är snällare, men lika tydlig."
    ),
    10: (
        "🎃 Oktober stänger – spöken och tidrapporten väntar",
        "Halloween är den 31 oktober. Och vad som är ännu läskigare? "
        "En tidrapporten som inte är stängd i tid."
    ),
    11: (
        "🍂 November – mörkt ute, klart i TicTac",
        "November är statisktiskt sett den månad då flest glömmer att tidrapportera. "
        "(Det stämmer möjligen inte – men känn av trycket ändå.)"
    ),
    12: (
        "🎄 December – årets sista tidrapport",
        "Det är årets sista chans att visa att du kan kombinera julstämning med "
        "administrativa rutiner. Spoiler: det kan du."
    ),
}


# ---------------------------------------------------------------------------
# API-hjälpare
# ---------------------------------------------------------------------------

def get_group_id(headers, name_contains):
    resp = requests.get(f"{API}/groups.json", headers=headers)
    resp.raise_for_status()
    groups = resp.json()
    group = next((g for g in groups if name_contains in g["full_name"]), None)
    if not group:
        raise Exception(f"Kunde inte hitta community med '{name_contains}'")
    return group["id"], group["full_name"]


def post_message(headers, group_id, body, mentioned_user_ids=None):
    data = {"body": body, "group_id": group_id}
    params = []
    if mentioned_user_ids:
        for uid in mentioned_user_ids:
            params.append(("mentioned_user_ids[]", uid))
    resp = requests.post(
        f"{API}/messages.json",
        headers=headers,
        data=data,
        params=params if params else None
    )
    return resp


# ---------------------------------------------------------------------------
# Meddelandebyggare
# ---------------------------------------------------------------------------

def build_message(month: int, month_name: str) -> str:
    title, intro = MONTH_INTROS.get(month, (
        f"📅 Sista arbetsdagen i {month_name}",
        f"Månaden är slut och det är dags att stänga {month_name}."
    ))

    return f"""📅 {title}

{intro}

Det betyder att tidrapporten för {month_name} ska vara klar idag.
På måndag morgon attesterar vi (jag och Henrik), sedan kör Annelie igång med fakturering.

Så innan du börjar planera nästa månad:
✅ Säkerställ att {month_name} är stängd och klar i TicTac
✅ Och i eventuella andra system du tidrapporterar i

Ordning och reda.
Alltid."""


MONTH_NAMES = [
    "", "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december"
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    today = date.today()

    if not is_last_working_day_today():
        lwd = last_working_day(today.year, today.month)
        print(f"Idag ({today}) är inte sista arbetsdagen i månaden.")
        print(f"Sista arbetsdagen är: {lwd}")
        print("Inget inlägg postas.")
        return

    # Dublettkoll: hoppa över om vi redan postat den här månaden
    marker_key = f"{today.year}-{today.month:02d}"
    if POSTED_MARKER.exists() and POSTED_MARKER.read_text().strip() == marker_key:
        print(f"Påminnelse redan postad för {marker_key}. Inget nytt inlägg.")
        return

    token = get_token("jesper")
    headers = {"Authorization": f"Bearer {token}"}

    month_name = MONTH_NAMES[today.month]
    print(f"✅ Idag är sista arbetsdagen i {month_name} {today.year} – postar påminnelse!")

    group_id, group_name = get_group_id(headers, TARGET_GROUP)
    print(f"Community: {group_name}")

    message = build_message(today.month, month_name)

    print("\n--- Förhandsgranskning ---")
    print(message)
    print("-" * 50)

    resp = post_message(
        headers,
        group_id,
        message,
        mentioned_user_ids=[HENRIK_ID, ANNELIE_ID]
    )

    if resp.ok:
        POSTED_MARKER.write_text(marker_key)
        print(f"✅ Påminnelse för {month_name} {today.year} postad!")
    else:
        print(f"❌ Fel: {resp.status_code} – {resp.text[:300]}")


if __name__ == "__main__":
    main()
