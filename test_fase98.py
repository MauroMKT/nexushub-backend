"""Test end-to-end ad-hoc per Fase 9.8 (non fa parte della suite ufficiale):
1) Contact -> Client conversion (POST /clients/from-contact/{id}), incluso idempotenza.
2) Invio campagna email: 400 se SMTP non configurato, poi invio reale contro
   un server SMTP locale fittizio (aiosmtpd non disponibile: usiamo un mock
   di smtplib.SMTP per verificare la logica senza dipendenze di rete).
"""
import os
import sys
import tempfile
from unittest import mock

tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.name}"

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

# --- Registrazione tenant di test ---
reg_payload = {
    "account_type": "persona_fisica",
    "language": "it",
    "full_name": "Mario Rossi",
    "admin_full_name": "Mario Rossi",
    "admin_email": "mario@example.com",
    "admin_password": "password123",
}
r = client.post("/auth/register", json=reg_payload)
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("=== TEST 1: Contact -> Client conversion ===")

r = client.post("/contacts", json={
    "full_name": "Giulia Bianchi",
    "email": "giulia@example.com",
    "phone": "3331234567",
    "company": "Bianchi Srl",
    "category": "fornitore",
    "notes": "Conosciuta a una fiera",
}, headers=headers)
assert r.status_code == 200, r.text
contact = r.json()
print("Contatto creato:", contact["id"], contact["category"])

r = client.post(f"/clients/from-contact/{contact['id']}", headers=headers)
assert r.status_code == 200, r.text
new_client = r.json()
assert new_client["name"] == "Giulia Bianchi"
assert new_client["email"] == "giulia@example.com"
assert new_client["company"] == "Bianchi Srl"
print("Cliente creato da contatto:", new_client["id"], new_client["name"])

r = client.get("/contacts", headers=headers)
updated_contact = next(c for c in r.json() if c["id"] == contact["id"])
assert updated_contact["client_id"] == new_client["id"], updated_contact
assert updated_contact["category"] == "cliente", updated_contact
print("Contatto ora collegato al cliente e categoria aggiornata a 'cliente' — OK")

# Idempotenza: richiamare l'endpoint non deve creare un secondo cliente
r = client.post(f"/clients/from-contact/{contact['id']}", headers=headers)
assert r.status_code == 200, r.text
again = r.json()
assert again["id"] == new_client["id"], "doveva restituire lo stesso cliente, non crearne uno nuovo"
r = client.get("/clients", headers=headers)
clients_with_that_email = [c for c in r.json() if c["email"] == "giulia@example.com"]
assert len(clients_with_that_email) == 1, f"attesi 1 cliente, trovati {len(clients_with_that_email)}"
print("Idempotenza OK: nessun duplicato creato al secondo tentativo")

# Contatto inesistente -> 404
r = client.post("/clients/from-contact/non-esiste", headers=headers)
assert r.status_code == 404
print("404 su contatto inesistente — OK\n")

print("=== TEST 2: invio campagna email ===")

r = client.post("/email/campaigns", json={
    "title": "Newsletter test",
    "subject": "Ciao!",
    "body_html": "<p>Contenuto di prova</p>",
}, headers=headers)
assert r.status_code == 200, r.text
camp = r.json()
assert camp["status"] == "draft"
print("Campagna creata, status iniziale:", camp["status"])

# Senza SMTP configurato -> 400
r = client.post(f"/email/campaigns/{camp['id']}/send", headers=headers)
assert r.status_code == 400, r.text
print("400 senza SMTP configurato — OK:", r.json()["detail"])

# Configuro SMTP del tenant
r = client.put("/settings/tenant", json={
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_username": "user@example.com",
    "smtp_password": "secret",
    "smtp_from_email": "invii@example.com",
    "smtp_from_name": "Test Sender",
    "smtp_use_tls": True,
}, headers=headers)
assert r.status_code == 200, r.text
tenant_out = r.json()
assert tenant_out["smtp_configured"] is True
assert "smtp_password" not in tenant_out, "la password SMTP non deve mai comparire nell'output API"
print("SMTP configurato, smtp_configured=True, password assente dall'output — OK")

# Senza destinatari con email valida -> 400. Il tenant "persona_fisica" non ha
# clienti/contatti con email tranne "giulia@example.com" già creata sopra, e
# non ha altri client con email: quindi c'è già 1 destinatario. Verifichiamo
# invece il caso zero-destinatari su un secondo tenant pulito.
reg_payload2 = dict(reg_payload, admin_email="anna@example.com", full_name="Anna Verdi", admin_full_name="Anna Verdi")
r = client.post("/auth/register", json=reg_payload2)
token2 = r.json()["access_token"]
headers2 = {"Authorization": f"Bearer {token2}"}
r = client.put("/settings/tenant", json={
    "smtp_host": "smtp.example.com", "smtp_from_email": "invii2@example.com",
}, headers=headers2)
assert r.status_code == 200, r.text
r = client.post("/email/campaigns", json={"title": "x", "subject": "y", "body_html": "z"}, headers=headers2)
camp2 = r.json()
r = client.post(f"/email/campaigns/{camp2['id']}/send", headers=headers2)
assert r.status_code == 400, r.text
print("400 senza destinatari — OK:", r.json()["detail"])

# Ora testiamo l'invio reale mockando smtplib.SMTP (niente rete disponibile in sandbox)
sent_calls = []

class FakeSMTP:
    def __init__(self, host, port, timeout=20):
        sent_calls.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self):
        sent_calls.append(("starttls",))

    def login(self, u, p):
        sent_calls.append(("login", u, p))

    def sendmail(self, from_addr, to_addrs, msg):
        sent_calls.append(("sendmail", from_addr, tuple(to_addrs)))


with mock.patch("app.email_sender.smtplib.SMTP", FakeSMTP):
    r = client.post(f"/email/campaigns/{camp['id']}/send", headers=headers)
    assert r.status_code == 200, r.text
    result = r.json()

print("Risultato invio:", {k: result[k] for k in ("sent_count", "failed_count", "status")})
assert result["sent_count"] == 1, result
assert result["failed_count"] == 0, result
assert result["status"] == "sent", result
assert any(call[0] == "sendmail" and call[2] == ("giulia@example.com",) for call in sent_calls), sent_calls
print("Invio reale via SMTP (mock) confermato: 1 email inviata a giulia@example.com — OK")

# Simuliamo un fallimento SMTP (es. autenticazione errata) e verifichiamo failed_count
class FailingSMTP(FakeSMTP):
    def sendmail(self, from_addr, to_addrs, msg):
        raise Exception("535 Authentication failed")

with mock.patch("app.email_sender.smtplib.SMTP", FailingSMTP):
    r = client.post(f"/email/campaigns/{camp['id']}/send", headers=headers)
    assert r.status_code == 200, r.text
    result2 = r.json()
assert result2["sent_count"] == 0, result2
assert result2["failed_count"] == 1, result2
assert result2["status"] == "failed", result2
print("Fallimento SMTP gestito correttamente: sent=0, failed=1, status=failed — OK")

os.unlink(tmp_db.name)
print("\nTUTTI I TEST FASE 9.8 SUPERATI")
