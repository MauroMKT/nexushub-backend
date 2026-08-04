"""Test end-to-end ad-hoc per l'estensione del modulo "Servizi IT & Marketing"
(Fase 9.16): milestone, time tracking reale e documenti/deliverable."""
import base64
import os
import sqlite3
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
    "full_name": "Agenzia Creativa", "admin_full_name": "Sara Neri",
    "admin_email": "sara@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.post("/modules/servizi_marketing", headers=headers)
if r.status_code == 402:
    conn = sqlite3.connect(tmp_db.name)
    conn.execute("UPDATE tenants SET plan = 'premium'")
    conn.commit()
    conn.close()
    r = client.post("/modules/servizi_marketing", headers=headers)
assert r.status_code == 200, r.text

print("=== TEST: creazione progetto retainer ===")
r = client.post("/agency/projects", json={
    "title": "Sito + SEO Cliente X", "is_retainer": True, "retainer_monthly": 1500,
    "hours_budget": 20, "notes": "Retainer mensile",
}, headers=headers)
assert r.status_code == 200, r.text
project = r.json()
assert project["hours_logged"] == 0 and project["hours_remaining"] == 20 and project["over_budget"] is False
project_id = project["id"]
print("Creazione progetto retainer con monte ore — OK")

print("=== TEST: milestone ===")
r = client.post(f"/agency/projects/{project_id}/milestones", json={
    "title": "Consegna wireframe", "due_date": "2026-08-15T00:00:00", "status": "in_corso",
}, headers=headers)
assert r.status_code == 200, r.text
milestone_id = r.json()["id"]
r = client.get(f"/agency/projects/{project_id}/milestones", headers=headers)
assert r.status_code == 200 and len(r.json()) == 1
r = client.patch(f"/agency/projects/{project_id}/milestones/{milestone_id}", json={"status": "completato"}, headers=headers)
assert r.status_code == 200 and r.json()["status"] == "completato"
r = client.get("/agency/projects", headers=headers)
assert next(p for p in r.json() if p["id"] == project_id)["milestone_count"] == 1
print("Creazione, lettura, aggiornamento milestone + milestone_count — OK")

print("=== TEST: time tracking reale ===")
r = client.post(f"/agency/projects/{project_id}/time-entries", json={
    "member_label": "Sara", "hours": 6, "description": "Wireframe homepage",
}, headers=headers)
assert r.status_code == 200, r.text
entry1_id = r.json()["id"]
r = client.post(f"/agency/projects/{project_id}/time-entries", json={
    "member_label": "Marco", "hours": 5.5, "description": "SEO tecnica",
}, headers=headers)
assert r.status_code == 200, r.text

r = client.get("/agency/projects", headers=headers)
p = next(p for p in r.json() if p["id"] == project_id)
assert p["hours_logged"] == 11.5 and abs(p["hours_remaining"] - 8.5) < 0.001 and p["over_budget"] is False
print("Voci di rendicontazione sommate correttamente in hours_logged — OK")

print("=== TEST: ore non positive rifiutate ===")
r = client.post(f"/agency/projects/{project_id}/time-entries", json={"hours": 0}, headers=headers)
assert r.status_code == 400, r.text
print("Validazione ore positive — OK")

print("=== TEST: rimozione voce ricalcola hours_logged ===")
r = client.delete(f"/agency/projects/{project_id}/time-entries/{entry1_id}", headers=headers)
assert r.status_code == 200
r = client.get("/agency/projects", headers=headers)
p = next(p for p in r.json() if p["id"] == project_id)
assert p["hours_logged"] == 5.5
print("Cancellazione voce di rendicontazione ricalcola il totale — OK")

print("=== TEST: superamento budget ore segnalato ===")
r = client.post(f"/agency/projects/{project_id}/time-entries", json={"hours": 20}, headers=headers)
assert r.status_code == 200
r = client.get("/agency/projects", headers=headers)
p = next(p for p in r.json() if p["id"] == project_id)
assert p["over_budget"] is True
print("over_budget=True quando le ore superano il monte ore — OK")

print("=== TEST: hours_logged manuale ignorato via PATCH ===")
r = client.patch(f"/agency/projects/{project_id}", json={"hours_logged": 0}, headers=headers)
assert r.status_code == 200
r = client.get("/agency/projects", headers=headers)
p = next(p for p in r.json() if p["id"] == project_id)
assert p["hours_logged"] == 25.5  # invariato: derivato dalle time entry, non dal PATCH manuale
print("hours_logged non sovrascrivibile manualmente — OK")

print("=== TEST: documenti/deliverable ===")
content = base64.b64encode(b"contratto firmato finto").decode()
r = client.post(f"/agency/projects/{project_id}/documents", json={
    "filename": "contratto.pdf", "content_type": "application/pdf", "content_base64": content,
}, headers=headers)
assert r.status_code == 200, r.text
doc_id = r.json()["id"]
r = client.get("/agency/projects", headers=headers)
assert next(p for p in r.json() if p["id"] == project_id)["document_count"] == 1
r = client.get(f"/agency/projects/{project_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200 and r.json()["content_base64"] == content
r = client.delete(f"/agency/projects/{project_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200
print("Upload, lettura e cancellazione deliverable — OK")

print("=== TEST: cancellazione progetto rimuove milestone/time-entry/documenti a cascata ===")
r = client.delete(f"/agency/projects/{project_id}", headers=headers)
assert r.status_code == 200
print("Cancellazione progetto — OK")

print("\nTUTTI I TEST ESTENSIONE SERVIZI IT & MARKETING SUPERATI")
