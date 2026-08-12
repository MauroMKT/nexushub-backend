"""
Report di sola lettura sui doppioni in Clienti (clients) e Rubrica (contacts).
NON modifica nulla nel database: mostra solo cosa verrebbe unito se poi si
esegue `python -m app.dedupe_merge`.

Uso:
    python -m app.dedupe_report
"""
from sqlalchemy import text

from .database import SessionLocal
from .dedupe_common import (build_groups, choose_primary, client_match_keys,
                             compute_merge_plan, contact_match_keys)


def _fetch_tenants(db):
    rows = db.execute(text("SELECT id, name FROM tenants ORDER BY name")).mappings().all()
    return [dict(r) for r in rows]


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


def _print_group(kind, tenant_name, group, name_field, fields, email_field, phone_field):
    primary, others = choose_primary(group, fields)
    plan = compute_merge_plan(primary, others, email_field=email_field, phone_field=phone_field)
    print(f"\n  Gruppo {kind} ({len(group)} schede) — azienda: {tenant_name}")
    print(f"    -> SCHEDA PRINCIPALE (verrebbe mantenuta): {primary.get(name_field)!r} "
          f"[id={primary['id']}] email={primary.get(email_field)!r} tel={primary.get(phone_field)!r} "
          f"creata il {primary.get('created_at')}")
    for o in others:
        print(f"       - verrebbe unita e poi eliminata: {o.get(name_field)!r} [id={o['id']}] "
              f"email={o.get(email_field)!r} tel={o.get(phone_field)!r} creata il {o.get('created_at')}")
    if plan["secondary_email"]:
        print(f"    -> email secondaria che verrebbe salvata: {plan['secondary_email']}")
    if plan["secondary_phone"]:
        print(f"    -> telefono secondario che verrebbe salvato: {plan['secondary_phone']}")
    for note in plan["overflow_notes"]:
        print(f"    -> in nota: {note}")


def run():
    db = SessionLocal()
    total_client_groups = 0
    total_contact_groups = 0
    try:
        tenants = _fetch_tenants(db)
        print(f"Aziende (tenant) trovate: {len(tenants)}")

        for t in tenants:
            clients = _fetch_clients(db, t["id"])
            client_groups = build_groups(clients, client_match_keys())
            for g in client_groups:
                _print_group("CLIENTE", t["name"], g, "name",
                              ["email", "phone", "whatsapp", "company"], "email", "phone")
            total_client_groups += len(client_groups)

            contacts = _fetch_contacts(db, t["id"])
            contact_groups = build_groups(contacts, contact_match_keys())
            for g in contact_groups:
                _print_group("CONTATTO RUBRICA", t["name"], g, "full_name",
                              ["email", "phone", "mobile", "whatsapp", "company"], "email", "phone")
            total_contact_groups += len(contact_groups)

        print("\n" + "=" * 70)
        print(f"TOTALE: {total_client_groups} gruppi di clienti doppi, "
              f"{total_contact_groups} gruppi di contatti rubrica doppi.")
        print("Nessuna modifica è stata fatta al database (questo è solo un report).")
        print("Se il risultato ti sembra corretto, esegui: python -m app.dedupe_merge")
    finally:
        db.close()


if __name__ == "__main__":
    run()
