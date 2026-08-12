"""
Esegue DAVVERO l'unione dei doppioni in Clienti (clients) e Rubrica (contacts).

NON eseguire questo script senza aver prima guardato l'output di
`python -m app.dedupe_report` ed essersi assicurati che i gruppi trovati
abbiano senso.

Cosa fa, per ogni azienda (tenant) separatamente:
  1. Aggiunge (se mancano) le colonne "secondary_email" e "secondary_phone"
     a clients e contacts (operazione sicura, non tocca dati esistenti).
  2. Trova i gruppi di doppioni con la stessa logica di dedupe_report.py.
  3. Per ogni gruppo sceglie una scheda "principale" (quella con più campi
     compilati) e vi salva email/telefono trovati nelle altre schede del
     gruppo, se diversi, nei campi secondari (o in nota se ce ne sono più di 2).
  4. Sposta su di essa tutto quello che era collegato alle altre schede del
     gruppo (trattative, appuntamenti, task, fatture, messaggi, moduli di
     settore, tag, ecc.) e poi elimina le schede duplicate.
  5. Se due schede duplicate hanno ENTRAMBE un accesso al portale clienti,
     ne tiene solo uno (quello della scheda principale) e lo segnala.

Ogni gruppo viene unito in una propria transazione: se un gruppo desse errore,
gli altri gruppi già uniti restano validi e lo script continua con i successivi,
segnalando chiaramente cosa è andato storto.

Uso:
    python -m app.dedupe_merge
"""
from sqlalchemy import text

from .database import SessionLocal, engine
from .dedupe_common import (build_groups, choose_primary, client_match_keys,
                             compute_merge_plan, contact_match_keys)

# Tabelle con una colonna client_id "semplice" da riassegnare (nessun vincolo
# di unicità, nessuna logica speciale necessaria).
SIMPLE_CLIENT_FK_TABLES = [
    "deals", "appointments", "tasks", "whatsapp_messages", "contacts",
    "client_chat_messages", "client_documents", "invoices",
    "engineering_projects", "agency_projects", "real_estate_properties",
    "reservations", "gym_members", "sector_records",
]


def _ensure_columns():
    with engine.begin() as conn:
        for stmt in [
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS secondary_email VARCHAR",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS secondary_phone VARCHAR",
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS secondary_email VARCHAR",
            "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS secondary_phone VARCHAR",
        ]:
            conn.execute(text(stmt))
    print("Colonne secondary_email / secondary_phone verificate su clients e contacts.")


def _fetch_tenants(db):
    return [dict(r) for r in db.execute(text("SELECT id, name FROM tenants ORDER BY name")).mappings().all()]


def _fetch_clients(db, tenant_id):
    rows = db.execute(text("""
        SELECT id, name, company, email, phone, whatsapp, notes, created_at
        FROM clients WHERE tenant_id = :tid
    """), {"tid": tenant_id}).mappings().all()
    return [dict(r) for r in rows]


def _fetch_contacts(db, tenant_id):
    rows = db.execute(text("""
        SELECT id, full_name, company, email, phone, mobile, whatsapp, notes, created_at
        FROM contacts WHERE tenant_id = :tid
    """), {"tid": tenant_id}).mappings().all()
    return [dict(r) for r in rows]


def _append_notes(existing_notes, overflow_notes):
    if not overflow_notes:
        return existing_notes
    extra = "\n".join(overflow_notes)
    if existing_notes:
        return existing_notes + "\n" + extra
    return extra


def _merge_client_group(db, tenant_name, group):
    primary, others = choose_primary(group, ["email", "phone", "whatsapp", "company"])
    plan = compute_merge_plan(primary, others, email_field="email", phone_field="phone")
    other_ids = [o["id"] for o in others]
    primary_id = primary["id"]

    new_notes = _append_notes(primary.get("notes"), plan["overflow_notes"])

    db.execute(text("""
        UPDATE clients
        SET secondary_email = COALESCE(secondary_email, :sec_email),
            secondary_phone = COALESCE(secondary_phone, :sec_phone),
            notes = :notes
        WHERE id = :pid
    """), {"sec_email": plan["secondary_email"], "sec_phone": plan["secondary_phone"],
           "notes": new_notes, "pid": primary_id})

    # client_tags: evita di duplicare (client_id, tag_id) già presenti sul principale
    for oid in other_ids:
        db.execute(text("""
            INSERT INTO client_tags (client_id, tag_id)
            SELECT :pid, tag_id FROM client_tags AS ct
            WHERE ct.client_id = :oid
              AND NOT EXISTS (
                  SELECT 1 FROM client_tags AS ct2
                  WHERE ct2.client_id = :pid AND ct2.tag_id = ct.tag_id
              )
        """), {"pid": primary_id, "oid": oid})
        db.execute(text("DELETE FROM client_tags WHERE client_id = :oid"), {"oid": oid})

    # client_portal_users: vincolo di unicità su client_id, va gestito a parte
    for oid in other_ids:
        has_primary_portal = db.execute(
            text("SELECT 1 FROM client_portal_users WHERE client_id = :pid"),
            {"pid": primary_id}).first()
        other_portal = db.execute(
            text("SELECT id FROM client_portal_users WHERE client_id = :oid"),
            {"oid": oid}).first()
        if other_portal and not has_primary_portal:
            db.execute(text("UPDATE client_portal_users SET client_id = :pid WHERE client_id = :oid"),
                       {"pid": primary_id, "oid": oid})
        elif other_portal and has_primary_portal:
            print(f"    ATTENZIONE: la scheda unita [id={oid}] aveva un accesso portale clienti "
                  f"proprio, che è stato eliminato perché '{primary.get('name')}' ne ha già uno.")
            db.execute(text("DELETE FROM client_portal_users WHERE client_id = :oid"), {"oid": oid})

    for tbl in SIMPLE_CLIENT_FK_TABLES:
        for oid in other_ids:
            db.execute(text(f"UPDATE {tbl} SET client_id = :pid WHERE client_id = :oid"),
                       {"pid": primary_id, "oid": oid})

    for oid in other_ids:
        db.execute(text("DELETE FROM clients WHERE id = :oid"), {"oid": oid})

    print(f"  [OK] Uniti {len(other_ids)} doppioni nella scheda cliente "
          f"'{primary.get('name')}' [id={primary_id}] — azienda: {tenant_name}")


def _merge_contact_group(db, tenant_name, group):
    primary, others = choose_primary(group, ["email", "phone", "mobile", "whatsapp", "company"])
    plan = compute_merge_plan(primary, others, email_field="email", phone_field="phone")
    other_ids = [o["id"] for o in others]
    primary_id = primary["id"]

    new_notes = _append_notes(primary.get("notes"), plan["overflow_notes"])

    db.execute(text("""
        UPDATE contacts
        SET secondary_email = COALESCE(secondary_email, :sec_email),
            secondary_phone = COALESCE(secondary_phone, :sec_phone),
            notes = :notes
        WHERE id = :pid
    """), {"sec_email": plan["secondary_email"], "sec_phone": plan["secondary_phone"],
           "notes": new_notes, "pid": primary_id})

    for oid in other_ids:
        db.execute(text("DELETE FROM contacts WHERE id = :oid"), {"oid": oid})

    print(f"  [OK] Uniti {len(other_ids)} doppioni nel contatto rubrica "
          f"'{primary.get('full_name')}' [id={primary_id}] — azienda: {tenant_name}")


def run():
    _ensure_columns()
    db = SessionLocal()
    ok_clients = ok_contacts = errors = 0
    try:
        tenants = _fetch_tenants(db)
        for t in tenants:
            client_groups = build_groups(_fetch_clients(db, t["id"]), client_match_keys())
            for g in client_groups:
                try:
                    _merge_client_group(db, t["name"], g)
                    db.commit()
                    ok_clients += 1
                except Exception as e:
                    db.rollback()
                    errors += 1
                    print(f"  [ERRORE] Gruppo cliente non unito ({t['name']}): {e}")

            contact_groups = build_groups(_fetch_contacts(db, t["id"]), contact_match_keys())
            for g in contact_groups:
                try:
                    _merge_contact_group(db, t["name"], g)
                    db.commit()
                    ok_contacts += 1
                except Exception as e:
                    db.rollback()
                    errors += 1
                    print(f"  [ERRORE] Gruppo contatto non unito ({t['name']}): {e}")

        print("\n" + "=" * 70)
        print(f"Fatto. Gruppi clienti uniti: {ok_clients}. Gruppi contatti uniti: {ok_contacts}. "
              f"Errori: {errors}.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
