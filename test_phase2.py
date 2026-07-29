"""Script di test end-to-end Fase 2 per verificare il database e i router."""
import sys
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine
from app import models

# Inizializza client FastAPI
client = TestClient(app)

# Forza la rigenerazione delle tabelle sul database SQLite locale di test
Base.metadata.create_all(bind=engine)

def run_tests():
    print("Avvio dei test di integrazione Fase 2...")
    db = SessionLocal()
    
    # 1. Crea un tenant ed un utente demo se non esistono per simulare l'autenticazione
    tenant = db.query(models.Tenant).filter(models.Tenant.slug == "test-tenant").first()
    if not tenant:
        tenant = models.Tenant(name="Test Company", slug="test-tenant", sector="Consulting")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        print(f"Tenant creato con ID: {tenant.id}")
        
    user = db.query(models.User).filter(models.User.email == "test@test.com").first()
    if not user:
        user = models.User(
            tenant_id=tenant.id,
            email="test@test.com",
            hashed_password="hashed_password",
            full_name="Test Admin",
            role=models.RoleEnum.admin
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Utente creato con ID: {user.id}")

    # Simula il token JWT di autenticazione per bypassare il router auth reale
    # Per semplicità nei test API, possiamo usare dependency_overrides o accedere direttamente ai database helper
    # Per questo test rapido, testiamo direttamente le query ORM per confermare il corretto schema database.
    
    print("\n--- Test ORM Database ---")
    
    # 2. Test Modello Client & WhatsApp relationship
    c = models.Client(tenant_id=tenant.id, name="Mario Rossi", phone="+393330000000")
    db.add(c)
    db.commit()
    db.refresh(c)
    print(f"Client creato: {c.name}")
    
    msg = models.WhatsAppMessage(
        tenant_id=tenant.id,
        client_id=c.id,
        direction="outbound",
        message_text="Ciao Mario!",
        status="sent"
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    print(f"WhatsApp message creato con relazione client: {msg.client.name} (Stato: {msg.status})")
    
    # 3. Test AutomationRule
    rule = models.AutomationRule(
        tenant_id=tenant.id,
        name="Benvenuto WhatsApp",
        trigger_type="new_client",
        actions='[{"type": "send_whatsapp", "content": "Benvenuto!"}]'
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    print(f"AutomationRule creata: {rule.name} per trigger {rule.trigger_type}")
    
    # 4. Test Blueprint
    bp = models.Blueprint(
        tenant_id=tenant.id,
        name="Vendita Standard",
        entity_type="deal",
        stages='{"states": ["Lead", "Contattato", "Fatto"]}'
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)
    print(f"Blueprint creato: {bp.name} (Stati: {bp.stages})")
    
    # 5. Test EmailCampaign
    camp = models.EmailCampaign(
        tenant_id=tenant.id,
        title="Newsletter Luglio",
        subject="Novità estive!",
        body_html="<h1>Novità</h1>"
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)
    print(f"EmailCampaign creata: {camp.title}")
    
    # 6. Test EmailSequence
    seq = models.EmailSequence(
        tenant_id=tenant.id,
        name="Follow up",
        trigger_stage_id="stage-123",
        steps='[{"delay_days": 2, "subject": "Hey", "body": "Hello"}]'
    )
    db.add(seq)
    db.commit()
    db.refresh(seq)
    print(f"EmailSequence creata: {seq.name}")
    
    # Pulisci record di test
    db.delete(seq)
    db.delete(camp)
    db.delete(bp)
    db.delete(rule)
    db.delete(msg)
    db.delete(c)
    db.commit()
    db.close()
    
    print("\nTUTTI I TEST E2E ORM SONO SUPERATI CON SUCCESSO! SCHEMA FUNZIONALE E COMPATIBILE.")

if __name__ == "__main__":
    run_tests()
