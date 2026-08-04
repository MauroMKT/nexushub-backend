"""Test end-to-end ad-hoc per l'estensione del modulo Agenzie Immobiliari
(Fase 9.13): nuovi campi immobile, galleria foto, documenti e video."""
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
from app.routers import realestate_router  # noqa: E402

client = TestClient(app)

r = client.post("/auth/register", json={
    "account_type": "persona_fisica", "language": "it",
    "full_name": "Agenzia Rossi", "admin_full_name": "Agenzia Rossi",
    "admin_email": "agenzia@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.post("/modules/agenzie_immobiliari", headers=headers)
if r.status_code == 402:
    conn = sqlite3.connect(tmp_db.name)
    conn.execute("UPDATE tenants SET plan = 'premium'")
    conn.commit()
    conn.close()
    r = client.post("/modules/agenzie_immobiliari", headers=headers)
assert r.status_code == 200, r.text


def b64(n_bytes):
    return base64.b64encode(b"A" * n_bytes).decode()


print("=== TEST: creazione immobile con tutti i nuovi campi ===")
payload = {
    "title": "Bilocale Via Roma", "property_type": "residenziale", "address": "Via Roma 10",
    "city": "Milano", "size_sqm": 65, "rooms": 3, "bathrooms": 1,
    "building_floor": "4", "unit_floor": "4", "contract_type": "vendita",
    "price": 220000, "valuation_price": 210000, "status": "disponibile",
    "condition_state": "buono", "visit_availability": "Lun-Ven 9-13, sabato su appuntamento",
    "rent_to_own": True, "video_url": "https://youtu.be/esempio", "notes": "Luminoso",
}
r = client.post("/real-estate/properties", json=payload, headers=headers)
assert r.status_code == 200, r.text
prop = r.json()
for k, v in payload.items():
    assert prop[k] == v, f"{k}: atteso {v!r}, ricevuto {prop[k]!r}"
assert prop["photo_count"] == 0
property_id = prop["id"]
print("Immobile creato con tutti i campi corretti — OK")

print("=== TEST: campo commerciale con riscatto (label dinamica lato frontend) ===")
r = client.post("/real-estate/properties", json={
    "title": "Locale commerciale Centro", "property_type": "commerciale", "contract_type": "locazione",
    "rent_to_own": True,
}, headers=headers)
assert r.status_code == 200, r.text
commercial_id = r.json()["id"]
assert r.json()["rent_to_own"] is True
print("Immobile commerciale con riscatto creato — OK")

print("=== TEST: galleria foto ===")
r = client.get(f"/real-estate/properties/{property_id}/photos", headers=headers)
assert r.status_code == 200 and r.json() == []

# foto valida (1 KB)
r = client.post(f"/real-estate/properties/{property_id}/photos",
                 json={"content_type": "image/jpeg", "content_base64": b64(1024)}, headers=headers)
assert r.status_code == 200, r.text
photo_id = r.json()["id"]
assert r.json()["size_bytes"] == 1024

r = client.get(f"/real-estate/properties/{property_id}/photos", headers=headers)
assert r.status_code == 200 and len(r.json()) == 1

r = client.get(f"/real-estate/properties/{property_id}/photos/{photo_id}", headers=headers)
assert r.status_code == 200 and r.json()["content_type"] == "image/jpeg"

# photo_count riflesso nella lista immobili
r = client.get("/real-estate/properties", headers=headers)
listed = next(p for p in r.json() if p["id"] == property_id)
assert listed["photo_count"] == 1, listed

# tipo non immagine rifiutato
r = client.post(f"/real-estate/properties/{property_id}/photos",
                 json={"content_type": "application/pdf", "content_base64": b64(1024)}, headers=headers)
assert r.status_code == 400, r.text

# dimensione oltre il limite (12 MB) rifiutata
oversized_photo = b64(realestate_router.MAX_PHOTO_SIZE_BYTES + 1024)
r = client.post(f"/real-estate/properties/{property_id}/photos",
                 json={"content_type": "image/jpeg", "content_base64": oversized_photo}, headers=headers)
assert r.status_code == 400, r.text
print("Upload/list/download foto + validazioni tipo e dimensione — OK")

r = client.delete(f"/real-estate/properties/{property_id}/photos/{photo_id}", headers=headers)
assert r.status_code == 200
r = client.get(f"/real-estate/properties/{property_id}/photos", headers=headers)
assert r.json() == []
r = client.get("/real-estate/properties", headers=headers)
listed = next(p for p in r.json() if p["id"] == property_id)
assert listed["photo_count"] == 0
print("Eliminazione foto + photo_count aggiornato — OK")

print("=== TEST: documenti (planimetrie/atti) ===")
r = client.post(f"/real-estate/properties/{property_id}/documents", json={
    "doc_type": "documento", "filename": "planimetria.pdf",
    "content_type": "application/pdf", "content_base64": b64(2048),
}, headers=headers)
assert r.status_code == 200, r.text
doc_id = r.json()["id"]
assert r.json()["uploaded_by_name"] == "Agenzia Rossi"

r = client.get(f"/real-estate/properties/{property_id}/documents", headers=headers)
assert r.status_code == 200 and len(r.json()) == 1
assert "content_base64" not in r.json()[0]  # lista senza contenuto, solo metadati

r = client.get(f"/real-estate/properties/{property_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200 and len(r.json()["content_base64"]) > 0

# documento oltre 20 MB rifiutato
oversized_doc = b64(realestate_router.MAX_DOCUMENT_SIZE_BYTES + 1024)
r = client.post(f"/real-estate/properties/{property_id}/documents", json={
    "doc_type": "documento", "filename": "troppo_grande.pdf",
    "content_type": "application/pdf", "content_base64": oversized_doc,
}, headers=headers)
assert r.status_code == 400, r.text
print("Upload/list/download documenti + limite dimensione — OK")

print("=== TEST: video ===")
r = client.post(f"/real-estate/properties/{property_id}/documents", json={
    "doc_type": "video", "filename": "presentazione.mp4",
    "content_type": "video/mp4", "content_base64": b64(4096),
}, headers=headers)
assert r.status_code == 200, r.text
video_id = r.json()["id"]
assert r.json()["doc_type"] == "video"

# content_type non video rifiutato per doc_type=video
r = client.post(f"/real-estate/properties/{property_id}/documents", json={
    "doc_type": "video", "filename": "non_e_un_video.pdf",
    "content_type": "application/pdf", "content_base64": b64(1024),
}, headers=headers)
assert r.status_code == 400, r.text

# video oltre 30 MB rifiutato
oversized_video = b64(realestate_router.MAX_VIDEO_SIZE_BYTES + 1024)
r = client.post(f"/real-estate/properties/{property_id}/documents", json={
    "doc_type": "video", "filename": "troppo_lungo.mp4",
    "content_type": "video/mp4", "content_base64": oversized_video,
}, headers=headers)
assert r.status_code == 400, r.text

r = client.get(f"/real-estate/properties/{property_id}/documents", headers=headers)
doc_types = sorted(d["doc_type"] for d in r.json())
assert doc_types == ["documento", "video"], doc_types
print("Upload video + validazione tipo/dimensione — OK")

print("=== TEST: eliminazione documento e video ===")
r = client.delete(f"/real-estate/properties/{property_id}/documents/{doc_id}", headers=headers)
assert r.status_code == 200
r = client.delete(f"/real-estate/properties/{property_id}/documents/{video_id}", headers=headers)
assert r.status_code == 200
r = client.get(f"/real-estate/properties/{property_id}/documents", headers=headers)
assert r.json() == []
print("Eliminazione documenti/video — OK")

print("=== TEST: 404 su immobile inesistente ===")
r = client.get("/real-estate/properties/non-esiste/photos", headers=headers)
assert r.status_code == 404
r = client.post("/real-estate/properties/non-esiste/photos",
                 json={"content_type": "image/jpeg", "content_base64": b64(10)}, headers=headers)
assert r.status_code == 404
r = client.get("/real-estate/properties/non-esiste/documents", headers=headers)
assert r.status_code == 404
print("404 coerenti su risorse figlie di un immobile inesistente — OK")

print("=== TEST: update parziale con nuovi campi ===")
r = client.patch(f"/real-estate/properties/{commercial_id}", json={
    "condition_state": "ristrutturato", "bathrooms": 2, "rent_to_own": False,
}, headers=headers)
assert r.status_code == 200, r.text
assert r.json()["condition_state"] == "ristrutturato"
assert r.json()["bathrooms"] == 2
assert r.json()["rent_to_own"] is False
print("PATCH parziale sui nuovi campi — OK")

print("\nTUTTI I TEST ESTENSIONE MODULO IMMOBILIARE SUPERATI")
