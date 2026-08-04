"""Test end-to-end ad-hoc per l'estensione del motore generico SectorWorkspace
(Fase 9.16): priorità, scadenza, assegnatario, tag, campi personalizzati e
documenti allegati, applicabili a tutti i ~17 settori generici del catalogo.
Usiamo "pmi" (piano free) come settore di prova."""
import base64
import os
import sys
import tempfile

tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.name}"
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

r = client.post("/auth/register", json={
    "account_type": "persona_fisica", "language": "it",
    "full_name": "PMI di Prova", "admin_full_name": "Luca Verdi",
    "admin_email": "luca@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.post("/modules/pmi", headers=headers)
assert r.status_code == 200, r.text

print("=== TEST: creazione elemento con tutti i nuovi campi ===")
r = client.post("/sector-records/pmi", json={
    "title": "Pratica Rossi", "priority": "alta", "due_date": "2026-09-01T10:00:00",
    "assigned_to": "Mario Bianchi", "tags": "urgente,cliente-vip",
    "custom_fields": {"partita_iva": "IT12345678901", "canale": "referral"},
    "notes": "Cliente storico",
}, headers=headers)
assert r.status_code == 200, r.text
record = r.json()
assert record["priority"] == "alta"
assert record["assigned_to"] == "Mario Bianchi"
assert record["tags"] == "urgente,cliente-vip"
assert record["custom_fields"] == {"partita_iva": "IT12345678901", "canale": "referral"}
assert record["document_count"] == 0
record_id = record["id"]
print("Creazione con priorità/scadenza/assegnatario/tag/campi personalizzati — OK")

print("=== TEST: priorità non valida rifiutata ===")
r = client.post("/sector-records/pmi", json={"title": "X", "priority": "urgentissima"}, headers=headers)
assert r.status_code == 400, r.text
print("Validazione priorità — OK")

print("=== TEST: update parziale campi personalizzati ===")
r = client.patch(f"/sector-records/pmi/{record_id}", json={
    "priority": "bassa", "custom_fields": {"canale": "sito web"},
}, headers=headers)
assert r.status_code == 200, r.text
assert r.json()["priority"] == "bassa"
assert r.json()["custom_fields"] == {"canale": "sito web"}
print("PATCH priorità + sostituzione campi personalizzati — OK")

print("=== TEST: documenti allegati ===")
content = base64.b64encode(b"contenuto pratica pdf finto").decode()
r = client.post(f"/sector-records/pmi/{record_id}/documents", json={
    "filename": "pratica.pdf", "content_type": "application/pdf", "content_base64": content,
}, headers=headers)
assert r.status_code == 200, r.text
doc_id = r.json()["id"]
assert r.json()["size_bytes"] > 0

r = client.get("/sector-records/pmi", headers=headers)
assert r.status_code == 200
assert next(x for x in r.json() if x["id"] == record_id)["document_count"] == 1

r = client.get(f"/sector-records/pmi/{record_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200 and r.json()["content_base64"] == content

r = client.delete(f"/sector-records/pmi/{record_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200
r = client.get("/sector-records/pmi", headers=headers)
assert next(x for x in r.json() if x["id"] == record_id)["document_count"] == 0
print("Upload, lettura e cancellazione documento + document_count coerente — OK")

print("=== TEST: isolamento multi-tenant ===")
r = client.post("/auth/register", json={
    "account_type": "persona_fisica", "language": "it",
    "full_name": "Altra PMI", "admin_full_name": "Altro Utente",
    "admin_email": "altropmi@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
other_token = r.json()["access_token"]
other_headers = {"Authorization": f"Bearer {other_token}"}
r = client.post("/modules/pmi", headers=other_headers)
assert r.status_code == 200, r.text

r = client.get("/sector-records/pmi", headers=other_headers)
assert r.status_code == 200 and r.json() == []
r = client.get(f"/sector-records/pmi/{record_id}/documents", headers=other_headers)
assert r.status_code == 404  # non vede l'elemento di un altro tenant
print("Isolamento multi-tenant confermato — OK")

print("\nTUTTI I TEST ESTENSIONE SECTORWORKSPACE SUPERATI")
