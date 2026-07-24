"""
Script di seed: crea un'azienda demo con dati di esempio per testare
subito la piattaforma senza passare dal form di registrazione.

Uso:
    python -m app.seed
"""
from datetime import datetime, timedelta

from .auth import hash_password
from .database import Base, SessionLocal, engine
from . import models

DEMO_STAGES = ["Nuovo Lead", "Contattato", "Proposta Inviata", "Trattativa", "Vinto", "Perso"]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Tenant).filter(models.Tenant.slug == "demo").first():
            print("Tenant demo già esistente, seed saltato.")
            return

        tenant = models.Tenant(name="Azienda Demo", slug="demo", sector="Consulenza",
                                default_language="it", plan="professional")
        db.add(tenant)
        db.flush()

        stages = []
        for idx, name in enumerate(DEMO_STAGES):
            stage = models.PipelineStage(tenant_id=tenant.id, name=name, order=idx)
            db.add(stage)
            stages.append(stage)
        db.flush()

        admin = models.User(
            tenant_id=tenant.id, email="admin@demo.nexushub.io",
            hashed_password=hash_password("Demo1234!"),
            full_name="Amministratore Demo", role=models.RoleEnum.admin, language="it",
        )
        db.add(admin)
        db.flush()

        tag_vip = models.Tag(tenant_id=tenant.id, name="VIP", color="#F6C6C0")
        tag_nuovo = models.Tag(tenant_id=tenant.id, name="Nuovo", color="#B8E0C8")
        db.add_all([tag_vip, tag_nuovo])
        db.flush()

        client1 = models.Client(tenant_id=tenant.id, name="Mario Rossi", company="Rossi Impianti Srl",
                                 email="mario.rossi@example.com", phone="+39 333 1234567",
                                 whatsapp="+39 333 1234567", sector="Edilizia", tags=[tag_vip])
        client2 = models.Client(tenant_id=tenant.id, name="Giulia Bianchi", company="Bianchi Design",
                                 email="giulia.bianchi@example.com", phone="+39 333 7654321",
                                 sector="Design", tags=[tag_nuovo])
        db.add_all([client1, client2])
        db.flush()

        db.add(models.Deal(tenant_id=tenant.id, client_id=client1.id, stage_id=stages[2].id,
                            title="Preventivo ristrutturazione", value=8500, currency="EUR"))
        db.add(models.Deal(tenant_id=tenant.id, client_id=client2.id, stage_id=stages[0].id,
                            title="Rebranding sito web", value=3200, currency="EUR"))

        now = datetime.utcnow()
        db.add(models.Appointment(
            tenant_id=tenant.id, client_id=client1.id, owner_user_id=admin.id,
            title="Sopralluogo cantiere", start_time=now + timedelta(days=1, hours=2),
            end_time=now + timedelta(days=1, hours=3), status=models.AppointmentStatus.scheduled,
        ))

        db.add(models.Task(
            tenant_id=tenant.id, assigned_user_id=admin.id, client_id=client2.id,
            title="Inviare bozza logo", due_date=now + timedelta(days=2),
        ))

        db.commit()
        print("Seed completato. Login demo -> email: admin@demo.nexushub.io / password: Demo1234!")
    finally:
        db.close()


if __name__ == "__main__":
    run()
