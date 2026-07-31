"""Cancellazione permanente e definitiva di un tenant e di tutti i suoi dati.

Non usa il cascade ORM di SQLAlchemy perché la maggior parte delle tabelle
tenant-scoped non ha una relationship dichiarata su Tenant (solo la colonna
tenant_id come foreign key): il cascade "all, delete-orphan" è definito solo
per Tenant.users e Tenant.clients. Per evitare violazioni di foreign key ed
essere certi di cancellare *tutti* i dati collegati, cancelliamo esplicitamente
riga per riga in ordine di dipendenza (figli prima dei genitori), in un'unica
transazione.

Operazione IRREVERSIBILE: non è un soft-delete. Il soft-delete esiste già
separatamente come sospensione (Tenant.is_active, vedi platform_admin_router).
Il chiamante deve aver già verificato permessi e conferme prima di invocare
hard_delete_tenant.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

# Ordine di cancellazione: le tabelle figlie prima delle tabelle a cui fanno
# riferimento via foreign key, così nessuna DELETE viola un vincolo.
_DELETE_STATEMENTS = [
    "DELETE FROM journal_lines WHERE entry_id IN (SELECT id FROM journal_entries WHERE tenant_id = :tid)",
    "DELETE FROM journal_entries WHERE tenant_id = :tid",
    "DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE tenant_id = :tid)",
    "DELETE FROM invoices WHERE tenant_id = :tid",
    "DELETE FROM chart_of_accounts WHERE tenant_id = :tid",
    "DELETE FROM google_calendar_connections WHERE tenant_id = :tid",
    "DELETE FROM client_documents WHERE tenant_id = :tid",
    "DELETE FROM client_chat_messages WHERE tenant_id = :tid",
    "DELETE FROM team_chat_messages WHERE tenant_id = :tid",
    "DELETE FROM chat_channels WHERE tenant_id = :tid",
    "DELETE FROM client_portal_users WHERE tenant_id = :tid",
    "DELETE FROM notifications WHERE tenant_id = :tid",
    "DELETE FROM contacts WHERE tenant_id = :tid",
    "DELETE FROM email_sequences WHERE tenant_id = :tid",
    "DELETE FROM email_campaigns WHERE tenant_id = :tid",
    "DELETE FROM whatsapp_templates WHERE tenant_id = :tid",
    "DELETE FROM whatsapp_messages WHERE tenant_id = :tid",
    "DELETE FROM blueprints WHERE tenant_id = :tid",
    "DELETE FROM automation_rules WHERE tenant_id = :tid",
    "DELETE FROM tasks WHERE tenant_id = :tid",
    "DELETE FROM appointments WHERE tenant_id = :tid",
    "DELETE FROM deals WHERE tenant_id = :tid",
    "DELETE FROM client_tags WHERE client_id IN (SELECT id FROM clients WHERE tenant_id = :tid)",
    "DELETE FROM tags WHERE tenant_id = :tid",
    "DELETE FROM pipeline_stages WHERE tenant_id = :tid",
    "DELETE FROM tenant_module_activations WHERE tenant_id = :tid",
    "DELETE FROM clients WHERE tenant_id = :tid",
    "DELETE FROM users WHERE tenant_id = :tid",
    "DELETE FROM tenants WHERE id = :tid",
]


def hard_delete_tenant(db: Session, tenant_id: str) -> None:
    """Cancella in modo permanente e irreversibile un tenant e tutti i dati
    collegati (utenti, clienti, trattative, fatture, chat, documenti, moduli
    attivati, ecc.). Il chiamante deve già aver verificato i permessi e le
    conferme necessarie prima di chiamare questa funzione."""
    for stmt in _DELETE_STATEMENTS:
        db.execute(text(stmt), {"tid": tenant_id})
    db.commit()
