"""Test end-to-end ad-hoc per data di nascita + notifiche compleanno (Fase 9.10)."""
import os
import sys
import sqlite3
import tempfile
from datetime import date, timedelta

tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.name}"
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

r = client.post("/auth/register", json={
    "account_type": "persona_fisica", "language": "it",
    "full_name": "Coach Rossi", "admin_full_name": "Coach Rossi",
    "admin_email": "coach@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.post("/modules/palestre", headers=headers)
if r.status_code == 402:
    conn = sqlite3.connect(tmp_db.name)
    conn.execute("UPDATE tenants SET plan = 'premium'")
    conn.commit()
    conn.close()
    r = client.post("/modules/palestre", headers=headers)
assert r.status_code == 200, r.text

today = date.today()


def iso(d):
    return d.isoformat()


print("=== TEST: creazione socio con data di nascita ===")
r = client.post("/gym/members", json={
    "full_name": "Compleanno Oggi", "phone": "3330000001", "email": "oggi@example.com",
    "address": "Via Uno 1", "birth_date": iso(today.replace(year=today.year - 30)),
}, headers=headers)
assert r.status_code == 200, r.text
member_today = r.json()
assert member_today["birth_date"] == iso(today.replace(year=today.year - 30))
print("Socio con birth_date creato e restituito correttamente — OK")

in_5_days = today + timedelta(days=5)
r = client.post("/gym/members", json={
    "full_name": "Compleanno Tra 5 Giorni", "phone": "3330000002", "email": "cinque@example.com",
    "address": "Via Due 2", "birth_date": iso(in_5_days.replace(year=in_5_days.year - 25)),
}, headers=headers)
assert r.status_code == 200, r.text
member_soon = r.json()

far_away = today + timedelta(days=200)
r = client.post("/gym/members", json={
    "full_name": "Compleanno Lontano", "phone": "3330000003", "email": "lontano@example.com",
    "address": "Via Tre 3", "birth_date": iso(far_away.replace(year=far_away.year - 40)),
}, headers=headers)
assert r.status_code == 200, r.text

r = client.post("/gym/members", json={
    "full_name": "Senza Data Nascita", "phone": "3330000004", "email": "senza@example.com",
    "address": "Via Quattro 4",
}, headers=headers)
assert r.status_code == 200, r.text
assert r.json()["birth_date"] is None
print("Socio senza data di nascita: campo opzionale, nessun errore — OK\n")

print("=== TEST: GET /gym/birthdays ===")
r = client.get("/gym/birthdays", headers=headers)
assert r.status_code == 200, r.text
board = r.json()
names = [e["full_name"] for e in board]
assert "Senza Data Nascita" not in names, "chi non ha birth_date non deve comparire"
assert "Compleanno Lontano" not in names, "oltre days_ahead=30 di default non deve comparire"
assert names[0] == "Compleanno Oggi", f"il compleanno di oggi deve essere primo, trovato: {names}"
assert board[0]["days_until"] == 0
assert board[0]["turning_age"] == 30
assert board[0]["notified_today"] is True
assert names[1] == "Compleanno Tra 5 Giorni"
assert board[1]["days_until"] == 5
assert board[1]["turning_age"] == 25
assert board[1]["notified_today"] is False
print("Ordinamento per prossimità, filtro days_ahead, età corretta — OK")

r = client.get("/gym/birthdays?days_ahead=250", headers=headers)
assert r.status_code == 200, r.text
names_wide = [e["full_name"] for e in r.json()]
assert "Compleanno Lontano" in names_wide
print("days_ahead più ampio include anche il compleanno lontano — OK\n")

print("=== TEST: notifica automatica per il compleanno di oggi (dedupe) ===")
r = client.get("/notifications", headers=headers)
assert r.status_code == 200, r.text
notifs = [n for n in r.json() if n.get("related_type") == "gym_birthday"]
assert len(notifs) == 1, f"attesa 1 notifica automatica, trovate {len(notifs)}"
assert "Compleanno Oggi" in notifs[0]["body"]
print("Notifica automatica creata una volta per il socio che compie gli anni oggi — OK")

# Richiamare di nuovo /gym/birthdays lo stesso giorno NON deve duplicare la notifica
r = client.get("/gym/birthdays", headers=headers)
assert r.status_code == 200, r.text
r = client.get("/notifications", headers=headers)
notifs_after = [n for n in r.json() if n.get("related_type") == "gym_birthday"]
assert len(notifs_after) == 1, f"la notifica automatica non deve duplicarsi nello stesso giorno, trovate {len(notifs_after)}"
print("Nessuna duplicazione richiamando /gym/birthdays più volte lo stesso giorno — OK\n")

print("=== TEST: invio manuale notifica compleanno ===")
r = client.post(f"/gym/members/{member_soon['id']}/birthday-notification", headers=headers)
assert r.status_code == 200, r.text
r = client.get("/notifications", headers=headers)
notifs_final = [n for n in r.json() if n.get("related_type") == "gym_birthday"]
assert len(notifs_final) == 2, f"attese 2 notifiche totali (1 auto + 1 manuale), trovate {len(notifs_final)}"
manual = next(n for n in notifs_final if "Tra 5 Giorni" in n["body"] or "Compleanno Tra 5 Giorni" in n["body"])
assert "compie 25 anni" in manual["body"] or "25 anni" in manual["body"]
print("Invio manuale crea una nuova notifica indipendente dal check automatico — OK")

# 404 su socio inesistente
r = client.post("/gym/members/non-esiste/birthday-notification", headers=headers)
assert r.status_code == 404, r.text

# 400 se il socio non ha birth_date
no_bday_id = client.get("/gym/members", headers=headers).json()
no_bday_member = next(m for m in no_bday_id if m["full_name"] == "Senza Data Nascita")
r = client.post(f"/gym/members/{no_bday_member['id']}/birthday-notification", headers=headers)
assert r.status_code == 400, r.text
print("400 su invio manuale per socio senza data di nascita — OK\n")

os.unlink(tmp_db.name)
print("TUTTI I TEST COMPLEANNI SUPERATI")
