"""Test end-to-end ad-hoc per il modulo Palestre (Fase 9.9)."""
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

# --- Registrazione + attivazione modulo "palestre" ---
r = client.post("/auth/register", json={
    "account_type": "persona_fisica", "language": "it",
    "full_name": "Coach Rossi", "admin_full_name": "Coach Rossi",
    "admin_email": "coach@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Il modulo palestre richiede piano premium: promuoviamo il tenant per il test
# via endpoint tenant settings non serve (plan non è in TenantUpdate) — usiamo
# platform_admin bootstrap? Più semplice: verifichiamo prima il 403 (modulo non
# attivo), poi controlliamo il piano minimo.
r = client.get("/gym/members", headers=headers)
assert r.status_code == 403, r.text
print("403 senza modulo attivo — OK")

r = client.post("/modules/palestre", headers=headers)
print("Tentativo attivazione modulo (piano free):", r.status_code, r.json())
# Il piano free non raggiunge "premium": atteso 402. Aggiorniamo il piano
# direttamente in DB per il test (non esiste un endpoint pubblico per farlo
# senza Stripe configurato).
if r.status_code == 402:
    import sqlite3
    conn = sqlite3.connect(tmp_db.name)
    conn.execute("UPDATE tenants SET plan = 'premium'")
    conn.commit()
    conn.close()
    r = client.post("/modules/palestre", headers=headers)
    assert r.status_code == 200, r.text
    print("Modulo attivato dopo upgrade piano — OK")
else:
    assert r.status_code == 200, r.text

r = client.get("/gym/members", headers=headers)
assert r.status_code == 200, r.text
assert r.json() == []
print("200 con modulo attivo, lista vuota — OK\n")

print("=== TEST: creazione socio ===")
r = client.post("/gym/members", json={
    "full_name": "Marco Verdi", "phone": "3331112222", "email": "marco@example.com",
    "address": "Via Roma 1, Milano", "fiscal_code": "VRDMRC90A01F205X",
    "card_number": "SOC-001", "federation_card_number": "FED-99887",
}, headers=headers)
assert r.status_code == 200, r.text
member = r.json()
member_id = member["id"]
assert member["medical_certificate_ok"] is False
assert member["has_photo"] is False
print("Socio creato:", member_id, member["full_name"])

# Campi obbligatori mancanti -> 422
r = client.post("/gym/members", json={"full_name": "Senza Contatti"}, headers=headers)
assert r.status_code == 422, r.text
print("422 su campi obbligatori mancanti (telefono/email/indirizzo) — OK\n")

print("=== TEST: corsi + iscrizione con grado (arti marziali) ===")
r = client.post(f"/gym/members/{member_id}/enrollments", json={
    "course_name": "Karate", "is_martial_arts": True,
    "grade_name": "Cintura Marrone", "grade_year": 2024,
}, headers=headers)
assert r.status_code == 200, r.text
member = r.json()
assert len(member["enrollments"]) == 1
enr = member["enrollments"][0]
assert enr["course_name"] == "Karate"
assert enr["is_martial_arts"] is True
assert enr["grade_name"] == "Cintura Marrone"
assert enr["grade_year"] == 2024
print("Iscrizione a corso nuovo (Karate) con grado — OK")

# Corso non-marziale: grado deve essere ignorato anche se passato
r = client.post(f"/gym/members/{member_id}/enrollments", json={
    "course_name": "Nuoto", "is_martial_arts": False, "grade_name": "ignorato",
}, headers=headers)
assert r.status_code == 200, r.text
member = r.json()
nuoto = next(e for e in member["enrollments"] if e["course_name"] == "Nuoto")
assert nuoto["grade_name"] is None, nuoto
print("Iscrizione a corso non marziale ignora il grado — OK")

# Riusa corso esistente case-insensitive invece di duplicare
r = client.post("/gym/courses", json={"name": "karate", "is_martial_arts": True}, headers=headers)
assert r.status_code == 200, r.text
r = client.get("/gym/courses", headers=headers)
courses = r.json()
karate_courses = [c for c in courses if c["name"].lower() == "karate"]
assert len(karate_courses) == 1, f"attesi 1 corso Karate, trovati {len(karate_courses)}"
print("Create-if-missing case-insensitive: nessun duplicato 'karate'/'Karate' — OK")

# Doppia iscrizione allo stesso corso -> 400
r = client.post(f"/gym/members/{member_id}/enrollments", json={"course_name": "Karate"}, headers=headers)
assert r.status_code == 400, r.text
print("400 su doppia iscrizione allo stesso corso — OK\n")

print("=== TEST: foto socio ===")
tiny_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 50).decode()
r = client.post(f"/gym/members/{member_id}/photo", json={
    "content_type": "image/png", "content_base64": tiny_png_b64,
}, headers=headers)
assert r.status_code == 200, r.text
assert r.json()["has_photo"] is True
r = client.get(f"/gym/members/{member_id}/photo", headers=headers)
assert r.status_code == 200, r.text
assert r.json()["content_base64"] == tiny_png_b64
print("Upload + download foto socio — OK")

# Formato non immagine rifiutato
r = client.post(f"/gym/members/{member_id}/photo", json={
    "content_type": "application/pdf", "content_base64": tiny_png_b64,
}, headers=headers)
assert r.status_code == 400, r.text
print("400 su foto con content_type non immagine — OK\n")

print("=== TEST: certificato medico + altri documenti ===")
pdf_b64 = base64.b64encode(b"%PDF-1.4 fake content").decode()
r = client.post(f"/gym/members/{member_id}/documents", json={
    "doc_type": "medical_certificate", "filename": "certificato.pdf",
    "content_type": "application/pdf", "content_base64": pdf_b64,
}, headers=headers)
assert r.status_code == 200, r.text
print("Upload certificato medico PDF — OK")

r = client.get(f"/gym/members/{member_id}", headers=headers)
assert r.json()["medical_certificate_ok"] is True, "il caricamento del certificato deve marcare ok=True automaticamente"
print("medical_certificate_ok settato automaticamente dopo l'upload — OK")

# Formato non ammesso per il certificato medico (es. .docx) -> 400
r = client.post(f"/gym/members/{member_id}/documents", json={
    "doc_type": "medical_certificate", "filename": "certificato.docx",
    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "content_base64": pdf_b64,
}, headers=headers)
assert r.status_code == 400, r.text
print("400 su certificato medico in formato non PDF/foto — OK")

# Altro documento libero, nessuna restrizione di formato
r = client.post(f"/gym/members/{member_id}/documents", json={
    "doc_type": "other", "filename": "liberatoria.docx",
    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "content_base64": pdf_b64,
}, headers=headers)
assert r.status_code == 200, r.text
print("Upload altro documento in formato libero — OK")

r = client.get(f"/gym/members/{member_id}/documents", headers=headers)
assert r.status_code == 200, r.text
docs = r.json()
assert len(docs) == 2
assert all("content_base64" not in d for d in docs), "la lista non deve includere il contenuto base64"
doc_id = docs[0]["id"]
r = client.get(f"/gym/members/{member_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200, r.text
assert "content_base64" in r.json()
print("Lista documenti senza contenuto + download con contenuto — OK\n")

print("=== TEST: trofei e classifica sociale ===")
r = client.post("/gym/members", json={
    "full_name": "Laura Bianchi", "phone": "3339998888", "email": "laura@example.com",
    "address": "Via Torino 2, Milano",
}, headers=headers)
member2_id = r.json()["id"]

for title, points in [("Campionato Regionale", 10), ("Torneo Cittadino", 5)]:
    r = client.post(f"/gym/members/{member_id}/trophies", json={"title": title, "points": points, "placement": "1°"}, headers=headers)
    assert r.status_code == 200, r.text

r = client.post(f"/gym/members/{member2_id}/trophies", json={"title": "Torneo Cittadino", "points": 20, "placement": "1°"}, headers=headers)
assert r.status_code == 200, r.text

r = client.get("/gym/leaderboard", headers=headers)
assert r.status_code == 200, r.text
board = r.json()
assert len(board) == 2
assert board[0]["member_id"] == member2_id, board  # 20 punti > 15 punti
assert board[0]["total_points"] == 20
assert board[1]["member_id"] == member_id
assert board[1]["total_points"] == 15
assert board[1]["trophies_count"] == 2
print("Classifica sociale ordinata per punti totali — OK:", [(e["full_name"], e["total_points"]) for e in board])

os.unlink(tmp_db.name)
print("\nTUTTI I TEST MODULO PALESTRE SUPERATI")
