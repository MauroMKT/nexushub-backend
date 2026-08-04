"""Test end-to-end ad-hoc per l'estensione del modulo "Servizi di Ingegneria"
(Fase 9.16): documenti/permessi, budget a consuntivo e storico cambi fase."""
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
    "full_name": "Studio Tecnico Bianchi", "admin_full_name": "Elena Bianchi",
    "admin_email": "elena@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.post("/modules/servizi_ingegneria", headers=headers)
if r.status_code == 402:
    conn = sqlite3.connect(tmp_db.name)
    conn.execute("UPDATE tenants SET plan = 'premium'")
    conn.commit()
    conn.close()
    r = client.post("/modules/servizi_ingegneria", headers=headers)
assert r.status_code == 200, r.text

print("=== TEST: creazione commessa con budget e referente ===")
r = client.post("/engineering/projects", json={
    "title": "Ampliamento capannone", "budget": 50000, "budget_actual": 12000,
    "assigned_to": "Ing. Rossi",
}, headers=headers)
assert r.status_code == 200, r.text
project = r.json()
assert project["budget_remaining"] == 38000 and project["over_budget"] is False
assert project["assigned_to"] == "Ing. Rossi"
project_id = project["id"]
print("Creazione con budget_actual/budget_remaining/assigned_to — OK")

print("=== TEST: storico fasi popolato alla creazione ===")
r = client.get(f"/engineering/projects/{project_id}/phase-log", headers=headers)
assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["phase"] == "progettazione"
print("Prima voce di storico fase registrata alla creazione — OK")

print("=== TEST: cambio fase aggiunge voce di storico ===")
r = client.patch(f"/engineering/projects/{project_id}", json={"phase": "permessi"}, headers=headers)
assert r.status_code == 200 and r.json()["phase"] == "permessi"
r = client.get(f"/engineering/projects/{project_id}/phase-log", headers=headers)
assert len(r.json()) == 2 and r.json()[1]["phase"] == "permessi"

# Un update che NON cambia la fase non deve aggiungere una nuova voce di storico.
r = client.patch(f"/engineering/projects/{project_id}", json={"phase": "permessi", "budget_actual": 15000}, headers=headers)
assert r.status_code == 200
r = client.get(f"/engineering/projects/{project_id}/phase-log", headers=headers)
assert len(r.json()) == 2
print("Storico fasi cresce solo quando la fase cambia davvero — OK")

print("=== TEST: superamento budget segnalato ===")
r = client.patch(f"/engineering/projects/{project_id}", json={"budget_actual": 55000}, headers=headers)
assert r.status_code == 200
assert r.json()["over_budget"] is True and r.json()["budget_remaining"] == -5000
print("over_budget=True e budget_remaining negativo quando si sfora — OK")

print("=== TEST: documenti/permessi ===")
content = base64.b64encode(b"permesso di costruire finto").decode()
r = client.post(f"/engineering/projects/{project_id}/documents", json={
    "filename": "permesso.pdf", "content_type": "application/pdf", "content_base64": content,
}, headers=headers)
assert r.status_code == 200, r.text
doc_id = r.json()["id"]
r = client.get("/engineering/projects", headers=headers)
assert next(p for p in r.json() if p["id"] == project_id)["document_count"] == 1
r = client.get(f"/engineering/projects/{project_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200 and r.json()["content_base64"] == content
r = client.delete(f"/engineering/projects/{project_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200
r = client.get("/engineering/projects", headers=headers)
assert next(p for p in r.json() if p["id"] == project_id)["document_count"] == 0
print("Upload, lettura e cancellazione documento/permesso — OK")

print("=== TEST: fase non valida rifiutata ===")
r = client.patch(f"/engineering/projects/{project_id}", json={"phase": "boh"}, headers=headers)
assert r.status_code == 400
print("Validazione fase — OK")

print("\nTUTTI I TEST ESTENSIONE SERVIZI DI INGEGNERIA SUPERATI")
