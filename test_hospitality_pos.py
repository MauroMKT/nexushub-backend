"""Test end-to-end ad-hoc per l'estensione POS del modulo Ristorazione &
Hospitality (Fase 9.15): profilo attività, mappa tavoli, comande cucina/
asporto/delivery, conto."""
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
    "full_name": "Trattoria Da Mario", "admin_full_name": "Mario Rossi",
    "admin_email": "mario@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.post("/modules/ristorazione", headers=headers)
if r.status_code == 402:
    conn = sqlite3.connect(tmp_db.name)
    conn.execute("UPDATE tenants SET plan = 'premium'")
    conn.commit()
    conn.close()
    r = client.post("/modules/ristorazione", headers=headers)
assert r.status_code == 200, r.text

print("=== TEST: profilo attività ===")
r = client.get("/hospitality/profile", headers=headers)
assert r.status_code == 200 and r.json()["business_type"] == "ristorante"
r = client.put("/hospitality/profile", json={"business_type": "hotel"}, headers=headers)
assert r.status_code == 200 and r.json()["business_type"] == "hotel"
r = client.put("/hospitality/profile", json={"business_type": "boh"}, headers=headers)
assert r.status_code == 400, r.text
r = client.put("/hospitality/profile", json={"business_type": "ristorante"}, headers=headers)
assert r.status_code == 200
print("Profilo attività letto/aggiornato + validazione — OK")

print("=== TEST: mappa tavoli ===")
r = client.post("/hospitality/tables", json={"label": "Tavolo 1", "seats": 4, "pos_x": 20, "pos_y": 30}, headers=headers)
assert r.status_code == 200, r.text
table1 = r.json()
assert table1["occupied"] is False
table1_id = table1["id"]

r = client.post("/hospitality/tables", json={"label": "Tavolo 2", "seats": 2, "pos_x": 60, "pos_y": 40}, headers=headers)
assert r.status_code == 200
table2_id = r.json()["id"]

r = client.get("/hospitality/tables", headers=headers)
assert r.status_code == 200 and len(r.json()) == 2

# Spostamento sulla mappa (drag & drop lato frontend -> PATCH posizione)
r = client.patch(f"/hospitality/tables/{table1_id}", json={"pos_x": 55, "pos_y": 70}, headers=headers)
assert r.status_code == 200 and r.json()["pos_x"] == 55 and r.json()["pos_y"] == 70
print("Creazione tavoli + spostamento posizione sulla mappa — OK")

print("=== TEST: voce di menu per la comanda ===")
r = client.post("/hospitality/menu-items", json={"name": "Margherita", "category": "primi", "price": 7.5}, headers=headers)
assert r.status_code == 200, r.text
pizza_id = r.json()["id"]

print("=== TEST: comanda al tavolo ===")
r = client.post("/hospitality/orders", json={
    "order_type": "tavolo", "table_id": table1_id,
    "items": [{"menu_item_id": pizza_id, "quantity": 2}, {"name": "Acqua naturale", "quantity": 1, "notes": "fredda"}],
}, headers=headers)
assert r.status_code == 200, r.text
order1 = r.json()
assert order1["status"] == "in_attesa"
assert order1["total"] == 7.5 * 2  # l'acqua senza prezzo pesa 0 nel totale (item libero)
assert order1["table_label"] == "Tavolo 1"
order1_id = order1["id"]

# tavolo ora risulta occupato
r = client.get("/hospitality/tables", headers=headers)
t1 = next(t for t in r.json() if t["id"] == table1_id)
assert t1["occupied"] is True and t1["open_order_count"] == 1
print("Creazione comanda al tavolo con item da menu + item libero — OK, tavolo occupato")

print("=== TEST: comanda senza tavolo per order_type=tavolo rifiutata ===")
r = client.post("/hospitality/orders", json={"order_type": "tavolo", "items": [{"name": "Pane", "quantity": 1}]}, headers=headers)
assert r.status_code == 400, r.text
r = client.post("/hospitality/orders", json={"order_type": "tavolo", "table_id": table1_id, "items": []}, headers=headers)
assert r.status_code == 400, r.text
print("Validazioni tavolo obbligatorio + almeno un item — OK")

print("=== TEST: schermata cucina — avanzamento stato ===")
r = client.get("/hospitality/orders?status=in_attesa,in_preparazione,pronto", headers=headers)
assert r.status_code == 200 and len(r.json()) == 1
r = client.patch(f"/hospitality/orders/{order1_id}/status", json={"status": "in_preparazione"}, headers=headers)
assert r.status_code == 200 and r.json()["status"] == "in_preparazione"
r = client.patch(f"/hospitality/orders/{order1_id}/status", json={"status": "pronto"}, headers=headers)
assert r.status_code == 200 and r.json()["status"] == "pronto"
r = client.patch(f"/hospitality/orders/{order1_id}/status", json={"status": "boh"}, headers=headers)
assert r.status_code == 400
print("Avanzamento stato comanda in_attesa -> in_preparazione -> pronto — OK")

print("=== TEST: asporto e delivery ===")
r = client.post("/hospitality/orders", json={
    "order_type": "asporto", "customer_name": "Luca Bianchi", "customer_phone": "3331234567",
    "items": [{"menu_item_id": pizza_id, "quantity": 1}],
}, headers=headers)
assert r.status_code == 200, r.text
takeaway_id = r.json()["id"]
assert r.json()["table_id"] is None

r = client.post("/hospitality/orders", json={
    "order_type": "delivery", "customer_name": "Anna Verdi", "customer_phone": "3339876543",
    "delivery_address": "Via Milano 10", "items": [{"menu_item_id": pizza_id, "quantity": 3}],
}, headers=headers)
assert r.status_code == 200, r.text
delivery_id = r.json()["id"]
assert r.json()["delivery_address"] == "Via Milano 10"

r = client.get("/hospitality/orders?order_type=delivery", headers=headers)
assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["id"] == delivery_id
print("Creazione ordini asporto/delivery + filtro per tipo — OK")

print("=== TEST: gestione ordini — lista completa senza filtri ===")
r = client.get("/hospitality/orders", headers=headers)
assert r.status_code == 200 and len(r.json()) == 3
print("Lista completa ordini per la schermata di gestione — OK")

print("=== TEST: conto al tavolo ===")
r = client.get(f"/hospitality/tables/{table1_id}/bill", headers=headers)
assert r.status_code == 200, r.text
preview = r.json()
assert preview["subtotal"] == 15.0 and len(preview["orders"]) == 1

r = client.post(f"/hospitality/tables/{table1_id}/bill/close", json={"discount": 1.5, "payment_method": "carta"}, headers=headers)
assert r.status_code == 200, r.text
bill = r.json()
assert bill["subtotal"] == 15.0 and bill["discount"] == 1.5 and bill["total"] == 13.5
assert bill["status"] == "pagato" and bill["table_label"] == "Tavolo 1"

# dopo la chiusura il tavolo torna libero
r = client.get("/hospitality/tables", headers=headers)
t1 = next(t for t in r.json() if t["id"] == table1_id)
assert t1["occupied"] is False and t1["open_order_count"] == 0

# non si può richiudere un conto già vuoto
r = client.post(f"/hospitality/tables/{table1_id}/bill/close", json={}, headers=headers)
assert r.status_code == 400
print("Preview conto + chiusura con sconto + tavolo liberato + doppia chiusura bloccata — OK")

print("=== TEST: conto singolo ordine (asporto) ===")
r = client.post(f"/hospitality/orders/{takeaway_id}/bill/close", json={"payment_method": "contanti"}, headers=headers)
assert r.status_code == 200, r.text
assert r.json()["subtotal"] == 7.5 and r.json()["table_id"] is None
r = client.post(f"/hospitality/orders/{takeaway_id}/bill/close", json={}, headers=headers)
assert r.status_code == 400, r.text  # già fatturato
print("Chiusura conto per singolo ordine asporto + blocco doppia fatturazione — OK")

print("=== TEST: storico conti ===")
r = client.get("/hospitality/bills", headers=headers)
assert r.status_code == 200 and len(r.json()) == 2
print("Storico conti — OK")

print("=== TEST: isolamento multi-tenant ===")
r = client.post("/auth/register", json={
    "account_type": "persona_fisica", "language": "it",
    "full_name": "Altro Ristorante", "admin_full_name": "Altro Utente",
    "admin_email": "altro@example.com", "admin_password": "password123",
})
assert r.status_code == 200, r.text
other_token = r.json()["access_token"]
other_headers = {"Authorization": f"Bearer {other_token}"}
r = client.post("/modules/ristorazione", headers=other_headers)
if r.status_code == 402:
    conn = sqlite3.connect(tmp_db.name)
    conn.execute("UPDATE tenants SET plan = 'premium' WHERE id != (SELECT tenant_id FROM users WHERE email = 'mario@example.com')")
    conn.commit()
    conn.close()
    r = client.post("/modules/ristorazione", headers=other_headers)
assert r.status_code == 200, r.text

r = client.get("/hospitality/tables", headers=other_headers)
assert r.status_code == 200 and r.json() == []  # non vede i tavoli dell'altro tenant
r = client.get(f"/hospitality/tables/{table2_id}/bill", headers=other_headers)
assert r.status_code == 404  # 404, non 200 con dati altrui
print("Isolamento multi-tenant su tavoli/conti confermato — OK")

print("\nTUTTI I TEST POS RISTORANTE SUPERATI")
