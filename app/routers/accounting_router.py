"""Gestionale contabilità completo (Fase 8, M20): piano dei conti, prima nota
(partita doppia), fatturazione con numerazione sequenziale, bilancio e conto
economico.

Principio guida: ogni fattura emessa o incassata genera automaticamente le
registrazioni di prima nota corrispondenti, cosi il bilancio resta sempre
coerente con le fatture senza che l'utente debba registrarle a mano due volte.

Nota di scope: la trasmissione allo SDI (fatturazione elettronica italiana)
richiede un provider terzo certificato ed è fuori dallo scope MVP; questo modulo
copre fatturazione, prima nota e bilancio in partita doppia completa."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/accounting", tags=["Gestionale Contabilità"])

BALANCE_EPSILON = 0.01

DEFAULT_ACCOUNTS = [
    ("1000", "Cassa", models.LedgerAccountType.asset),
    ("1010", "Banca", models.LedgerAccountType.asset),
    ("1100", "Crediti v/clienti", models.LedgerAccountType.asset),
    ("1200", "IVA a credito", models.LedgerAccountType.asset),
    ("2000", "Debiti v/fornitori", models.LedgerAccountType.liability),
    ("2100", "IVA a debito", models.LedgerAccountType.liability),
    ("3000", "Capitale sociale", models.LedgerAccountType.equity),
    ("3100", "Utili portati a nuovo", models.LedgerAccountType.equity),
    ("4000", "Ricavi da vendite", models.LedgerAccountType.revenue),
    ("5000", "Costi di gestione", models.LedgerAccountType.expense),
]


def _ensure_default_accounts(db: Session, tenant_id: str) -> List[models.ChartOfAccount]:
    existing = db.query(models.ChartOfAccount).filter(models.ChartOfAccount.tenant_id == tenant_id).all()
    if existing:
        return existing
    accounts = [
        models.ChartOfAccount(tenant_id=tenant_id, code=code, name=name, account_type=acc_type, is_system=True)
        for code, name, acc_type in DEFAULT_ACCOUNTS
    ]
    db.add_all(accounts)
    db.commit()
    for a in accounts:
        db.refresh(a)
    return accounts


def _get_account(db: Session, tenant_id: str, code: str) -> models.ChartOfAccount:
    acc = db.query(models.ChartOfAccount).filter(
        models.ChartOfAccount.tenant_id == tenant_id, models.ChartOfAccount.code == code
    ).first()
    if not acc:
        raise HTTPException(status_code=500, detail=f"Conto contabile mancante: {code}")
    return acc


def _post_journal_entry(db: Session, tenant_id: str, entry_date: datetime, description: str,
                         lines: List[dict], source: str, source_invoice_id: Optional[str] = None,
                         user_id: Optional[str] = None) -> models.JournalEntry:
    total_debit = sum(l["debit"] for l in lines)
    total_credit = sum(l["credit"] for l in lines)
    if abs(total_debit - total_credit) > BALANCE_EPSILON:
        raise HTTPException(
            status_code=400,
            detail=f"Registrazione non bilanciata: dare {total_debit:.2f} vs avere {total_credit:.2f}",
        )
    entry = models.JournalEntry(
        tenant_id=tenant_id, entry_date=entry_date, description=description,
        source=source, source_invoice_id=source_invoice_id, created_by_user_id=user_id,
    )
    db.add(entry)
    db.flush()
    for l in lines:
        db.add(models.JournalLine(
            entry_id=entry.id, account_id=l["account_id"], debit=l["debit"],
            credit=l["credit"], description=l.get("description"),
        ))
    db.commit()
    db.refresh(entry)
    return entry


def _next_invoice_number(db: Session, tenant: models.Tenant) -> str:
    year = datetime.utcnow().year
    if tenant.invoice_seq_year != year:
        tenant.invoice_seq_year = year
        tenant.invoice_seq_last = 0
    tenant.invoice_seq_last += 1
    db.commit()
    return f"{year}-{tenant.invoice_seq_last:04d}"


def _compute_invoice_totals(lines: List[schemas.InvoiceLineCreate]) -> tuple:
    subtotal = sum(l.quantity * l.unit_price for l in lines)
    vat_amount = sum(l.quantity * l.unit_price * (l.vat_rate / 100) for l in lines)
    return round(subtotal, 2), round(vat_amount, 2), round(subtotal + vat_amount, 2)


def _invoice_to_out(inv: models.Invoice, client_name: Optional[str] = None) -> schemas.InvoiceOut:
    line_outs = [
        schemas.InvoiceLineOut(id=l.id, description=l.description, quantity=l.quantity,
                                unit_price=l.unit_price, vat_rate=l.vat_rate)
        for l in inv.lines
    ]
    return schemas.InvoiceOut(
        id=inv.id, client_id=inv.client_id, client_name=client_name, number=inv.number,
        issue_date=inv.issue_date, due_date=inv.due_date, status=inv.status.value if hasattr(inv.status, "value") else inv.status,
        currency=inv.currency, notes=inv.notes, subtotal=inv.subtotal, vat_amount=inv.vat_amount,
        total=inv.total, paid_at=inv.paid_at, lines=line_outs,
    )


# ---------- Piano dei conti ----------
@router.get("/accounts", response_model=List[schemas.ChartOfAccountOut])
def list_accounts(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _ensure_default_accounts(db, user.tenant_id)


@router.post("/accounts", response_model=schemas.ChartOfAccountOut)
def create_account(payload: schemas.ChartOfAccountCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    if payload.account_type not in [t.value for t in models.LedgerAccountType]:
        raise HTTPException(status_code=400, detail="Tipo di conto non valido")
    account = models.ChartOfAccount(
        tenant_id=user.tenant_id, code=payload.code, name=payload.name,
        account_type=payload.account_type, is_system=False,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


# ---------- Prima nota ----------
@router.get("/journal-entries", response_model=List[schemas.JournalEntryOut])
def list_journal_entries(start: Optional[datetime] = None, end: Optional[datetime] = None,
                          db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.JournalEntry).filter(models.JournalEntry.tenant_id == user.tenant_id)
    if start:
        q = q.filter(models.JournalEntry.entry_date >= start)
    if end:
        q = q.filter(models.JournalEntry.entry_date <= end)
    entries = q.order_by(models.JournalEntry.entry_date.desc()).all()

    out = []
    for e in entries:
        line_outs = []
        for l in e.lines:
            line_outs.append(schemas.JournalLineOut(
                id=l.id, account_id=l.account_id, account_name=l.account.name if l.account else None,
                debit=l.debit, credit=l.credit, description=l.description,
            ))
        out.append(schemas.JournalEntryOut(
            id=e.id, entry_date=e.entry_date, description=e.description, source=e.source,
            source_invoice_id=e.source_invoice_id, lines=line_outs,
        ))
    return out


@router.post("/journal-entries", response_model=schemas.JournalEntryOut)
def create_journal_entry(payload: schemas.JournalEntryCreate, db: Session = Depends(get_db),
                          user: models.User = Depends(get_current_user)):
    if len(payload.lines) < 2:
        raise HTTPException(status_code=400, detail="Una registrazione richiede almeno due righe (dare e avere)")
    for l in payload.lines:
        acc = db.query(models.ChartOfAccount).filter(
            models.ChartOfAccount.id == l.account_id, models.ChartOfAccount.tenant_id == user.tenant_id
        ).first()
        if not acc:
            raise HTTPException(status_code=404, detail=f"Conto contabile non trovato: {l.account_id}")

    entry = _post_journal_entry(
        db, user.tenant_id, payload.entry_date, payload.description,
        [l.dict() for l in payload.lines], source="manual", user_id=user.id,
    )
    line_outs = [
        schemas.JournalLineOut(id=l.id, account_id=l.account_id, account_name=l.account.name, debit=l.debit,
                                credit=l.credit, description=l.description)
        for l in entry.lines
    ]
    return schemas.JournalEntryOut(
        id=entry.id, entry_date=entry.entry_date, description=entry.description, source=entry.source,
        source_invoice_id=entry.source_invoice_id, lines=line_outs,
    )


# ---------- Fatture ----------
@router.get("/invoices", response_model=List[schemas.InvoiceOut])
def list_invoices(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    invoices = db.query(models.Invoice).filter(models.Invoice.tenant_id == user.tenant_id).order_by(
        models.Invoice.created_at.desc()
    ).all()
    client_ids = {i.client_id for i in invoices}
    clients = {c.id: c.name for c in db.query(models.Client).filter(models.Client.id.in_(client_ids)).all()} if client_ids else {}
    return [_invoice_to_out(i, clients.get(i.client_id)) for i in invoices]


@router.post("/invoices", response_model=schemas.InvoiceOut)
def create_invoice(payload: schemas.InvoiceCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).filter(
        models.Client.id == payload.client_id, models.Client.tenant_id == user.tenant_id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    if not payload.lines:
        raise HTTPException(status_code=400, detail="La fattura deve avere almeno una riga")

    subtotal, vat_amount, total = _compute_invoice_totals(payload.lines)
    invoice = models.Invoice(
        tenant_id=user.tenant_id, client_id=payload.client_id, issue_date=payload.issue_date,
        due_date=payload.due_date, notes=payload.notes, status=models.InvoiceStatus.draft,
        subtotal=subtotal, vat_amount=vat_amount, total=total,
    )
    db.add(invoice)
    db.flush()
    for l in payload.lines:
        db.add(models.InvoiceLine(
            invoice_id=invoice.id, description=l.description, quantity=l.quantity,
            unit_price=l.unit_price, vat_rate=l.vat_rate,
        ))
    db.commit()
    db.refresh(invoice)
    return _invoice_to_out(invoice, client.name)


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id, models.Invoice.tenant_id == user.tenant_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    client = db.query(models.Client).filter(models.Client.id == invoice.client_id).first()
    return _invoice_to_out(invoice, client.name if client else None)


@router.post("/invoices/{invoice_id}/issue", response_model=schemas.InvoiceOut)
def issue_invoice(invoice_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Emette la fattura: assegna il numero sequenziale e registra in prima nota
    Crediti v/clienti (dare) contro Ricavi + IVA a debito (avere)."""
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id, models.Invoice.tenant_id == user.tenant_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    if invoice.status != models.InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Solo le fatture in bozza possono essere emesse")

    tenant = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
    _ensure_default_accounts(db, user.tenant_id)
    crediti = _get_account(db, user.tenant_id, "1100")
    ricavi = _get_account(db, user.tenant_id, "4000")
    iva_debito = _get_account(db, user.tenant_id, "2100")

    invoice.number = _next_invoice_number(db, tenant)
    invoice.status = models.InvoiceStatus.sent
    db.commit()
    db.refresh(invoice)

    client = db.query(models.Client).filter(models.Client.id == invoice.client_id).first()
    _post_journal_entry(
        db, user.tenant_id, invoice.issue_date, f"Emissione fattura {invoice.number} - {client.name if client else ''}",
        [
            {"account_id": crediti.id, "debit": invoice.total, "credit": 0, "description": "Crediti v/clienti"},
            {"account_id": ricavi.id, "debit": 0, "credit": invoice.subtotal, "description": "Ricavi"},
            {"account_id": iva_debito.id, "debit": 0, "credit": invoice.vat_amount, "description": "IVA a debito"},
        ],
        source="invoice_issued", source_invoice_id=invoice.id, user_id=user.id,
    )
    return _invoice_to_out(invoice, client.name if client else None)


@router.post("/invoices/{invoice_id}/mark-paid", response_model=schemas.InvoiceOut)
def mark_invoice_paid(invoice_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Registra l'incasso: Banca (dare) contro Crediti v/clienti (avere)."""
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id, models.Invoice.tenant_id == user.tenant_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    if invoice.status != models.InvoiceStatus.sent and invoice.status != models.InvoiceStatus.overdue:
        raise HTTPException(status_code=400, detail="Solo le fatture emesse possono essere segnate come incassate")

    banca = _get_account(db, user.tenant_id, "1010")
    crediti = _get_account(db, user.tenant_id, "1100")

    invoice.status = models.InvoiceStatus.paid
    invoice.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(invoice)

    client = db.query(models.Client).filter(models.Client.id == invoice.client_id).first()
    _post_journal_entry(
        db, user.tenant_id, invoice.paid_at, f"Incasso fattura {invoice.number} - {client.name if client else ''}",
        [
            {"account_id": banca.id, "debit": invoice.total, "credit": 0, "description": "Banca"},
            {"account_id": crediti.id, "debit": 0, "credit": invoice.total, "description": "Crediti v/clienti"},
        ],
        source="invoice_paid", source_invoice_id=invoice.id, user_id=user.id,
    )
    return _invoice_to_out(invoice, client.name if client else None)


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id, models.Invoice.tenant_id == user.tenant_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    if invoice.status != models.InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Solo le fatture in bozza possono essere eliminate")
    db.delete(invoice)
    db.commit()
    return {"ok": True}


# ---------- Bilancio e conto economico ----------
@router.get("/reports/balance-sheet", response_model=schemas.BalanceSheetOut)
def balance_sheet(as_of: Optional[datetime] = None, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    as_of = as_of or datetime.utcnow()
    accounts = _ensure_default_accounts(db, user.tenant_id)

    def section(acc_type: models.LedgerAccountType, credit_normal: bool) -> schemas.BalanceSheetSection:
        rows = []
        total = 0.0
        for acc in [a for a in accounts if a.account_type == acc_type]:
            lines = db.query(models.JournalLine).join(models.JournalEntry).filter(
                models.JournalLine.account_id == acc.id, models.JournalEntry.entry_date <= as_of,
            ).all()
            debit = sum(l.debit for l in lines)
            credit = sum(l.credit for l in lines)
            balance = (credit - debit) if credit_normal else (debit - credit)
            if abs(balance) > BALANCE_EPSILON:
                rows.append({"code": acc.code, "name": acc.name, "balance": round(balance, 2)})
                total += balance
        return schemas.BalanceSheetSection(account_type=acc_type.value, accounts=rows, total=round(total, 2))

    assets = section(models.LedgerAccountType.asset, credit_normal=False)
    liabilities = section(models.LedgerAccountType.liability, credit_normal=True)
    equity = section(models.LedgerAccountType.equity, credit_normal=True)

    # Ricavi e costi sono conti "di transito": senza una scrittura di chiusura
    # esercizio, il loro saldo non confluisce nel patrimonio netto e il bilancio
    # risulterebbe artificialmente sbilanciato. Come nei gestionali standard,
    # il risultato d'esercizio maturato viene quindi mostrato come riga sintetica
    # nel patrimonio netto, senza richiedere una scrittura di chiusura manuale.
    revenue_total = 0.0
    for acc in [a for a in accounts if a.account_type == models.LedgerAccountType.revenue]:
        lines = db.query(models.JournalLine).join(models.JournalEntry).filter(
            models.JournalLine.account_id == acc.id, models.JournalEntry.entry_date <= as_of,
        ).all()
        revenue_total += sum(l.credit for l in lines) - sum(l.debit for l in lines)
    expense_total = 0.0
    for acc in [a for a in accounts if a.account_type == models.LedgerAccountType.expense]:
        lines = db.query(models.JournalLine).join(models.JournalEntry).filter(
            models.JournalLine.account_id == acc.id, models.JournalEntry.entry_date <= as_of,
        ).all()
        expense_total += sum(l.debit for l in lines) - sum(l.credit for l in lines)
    net_income_to_date = round(revenue_total - expense_total, 2)
    if abs(net_income_to_date) > BALANCE_EPSILON:
        equity.accounts.append({"code": "3900", "name": "Risultato d'esercizio (provvisorio)", "balance": net_income_to_date})
        equity.total = round(equity.total + net_income_to_date, 2)

    return schemas.BalanceSheetOut(
        as_of=as_of, assets=assets, liabilities=liabilities, equity=equity,
        balanced=abs(assets.total - (liabilities.total + equity.total)) < BALANCE_EPSILON,
    )


@router.get("/reports/income-statement", response_model=schemas.IncomeStatementOut)
def income_statement(start: datetime, end: datetime, db: Session = Depends(get_db),
                      user: models.User = Depends(get_current_user)):
    accounts = _ensure_default_accounts(db, user.tenant_id)

    def section(acc_type: models.LedgerAccountType, credit_normal: bool) -> schemas.BalanceSheetSection:
        rows = []
        total = 0.0
        for acc in [a for a in accounts if a.account_type == acc_type]:
            lines = db.query(models.JournalLine).join(models.JournalEntry).filter(
                models.JournalLine.account_id == acc.id,
                models.JournalEntry.entry_date >= start, models.JournalEntry.entry_date <= end,
            ).all()
            debit = sum(l.debit for l in lines)
            credit = sum(l.credit for l in lines)
            balance = (credit - debit) if credit_normal else (debit - credit)
            if abs(balance) > BALANCE_EPSILON:
                rows.append({"code": acc.code, "name": acc.name, "balance": round(balance, 2)})
                total += balance
        return schemas.BalanceSheetSection(account_type=acc_type.value, accounts=rows, total=round(total, 2))

    revenue = section(models.LedgerAccountType.revenue, credit_normal=True)
    expenses = section(models.LedgerAccountType.expense, credit_normal=False)

    return schemas.IncomeStatementOut(
        start=start, end=end, revenue=revenue, expenses=expenses,
        net_income=round(revenue.total - expenses.total, 2),
    )
