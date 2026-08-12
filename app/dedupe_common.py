"""
Logica condivisa per l'unione dei doppioni in Clienti (clients) e Rubrica (contacts).

Usata sia da dedupe_report.py (sola lettura, mostra cosa verrebbe unito) sia da
dedupe_merge.py (esegue davvero l'unione). Tenerla in un unico posto garantisce
che il report mostrato all'utente corrisponda esattamente a quello che poi
succede per davvero.

Criterio di corrispondenza (due schede sono considerate "stesso cliente/contatto"
se almeno UNA di queste corrisponde, con collegamento transitivo: se A=B su
un criterio e B=C su un altro, A/B/C finiscono nello stesso gruppo):
  - stessa email (case-insensitive)
  - stesso numero di telefono/cellulare/whatsapp (confrontato sulle ultime 9 cifre,
    per non far fallire il confronto solo per il prefisso internazionale)
  - stesso nome (+ azienda, se presente)

Il confronto è sempre ristretto allo stesso tenant (stessa azienda cliente della
piattaforma): non unisce mai dati tra tenant diversi.
"""
import re
from collections import defaultdict

# Una vera email ha sempre la forma testo@testo.testo. Molte schede hanno nel
# campo email un promemoria testuale invece di una email vera (es. "verificare
# sito", "verificare email", "form sito", "da cercare su LinkedIn"...). Se questi
# testi identici venissero considerati "stessa email", schede di aziende/persone
# completamente diverse verrebbero unite per errore. Per questo consideriamo
# valida come chiave di confronto SOLO una stringa nel formato email vero.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Coppie di schede che NON vanno mai unite anche se condividono email/telefono/nome,
# perché una revisione manuale ha stabilito che sono entità distinte. Ogni voce è
# l'insieme dei due id record. Aggiungere qui altre coppie se emergono altri casi
# da tenere separati.
EXCLUDED_MERGE_PAIRS = {
    # 'SS Lazio Marketing & Communication SpA' vs 'Groupama Assicurazioni':
    # condividono l'email mktcomm@sslazio.it ma sono aziende diverse — da tenere separate.
    frozenset({"403c31dd-e1fb-4807-8568-12033c5fe7f8", "1823b4b6-0451-4f62-8f07-561733121fad"}),
}


def normalize_email(email):
    if not email:
        return None
    e = email.strip().lower()
    if not e or not _EMAIL_RE.match(e):
        return None
    return e


def normalize_phone(phone):
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 6:
        return None
    # confronta sulle ultime 9 cifre per assorbire differenze di prefisso
    # internazionale (es. "+39 333 1234567" vs "3331234567")
    return digits[-9:]


def normalize_name(name, company=None):
    if not name:
        return None
    n = re.sub(r"\s+", " ", name.strip().lower())
    c = re.sub(r"\s+", " ", (company or "").strip().lower())
    if not n:
        return None
    return f"{n}|{c}"


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def build_groups(records, key_fns, excluded_pairs=None):
    """
    records: lista di dict con almeno i campi usati da key_fns (e "id").
    key_fns: lista di funzioni record -> chiave normalizzata (o None).
    excluded_pairs: insieme di frozenset({id1, id2}) che non vanno mai unite,
        anche se condividono una chiave (es. revisione manuale che ha stabilito
        che sono entità distinte). Default: EXCLUDED_MERGE_PAIRS.
    Ritorna: lista di gruppi (ognuno lista di record), solo gruppi con 2+ elementi.
    """
    if excluded_pairs is None:
        excluded_pairs = EXCLUDED_MERGE_PAIRS
    n = len(records)
    ids = [r.get("id") for r in records]
    uf = UnionFind(n)
    for key_fn in key_fns:
        buckets = defaultdict(list)
        for i, r in enumerate(records):
            k = key_fn(r)
            if k:
                buckets[k].append(i)
        for idxs in buckets.values():
            if len(idxs) > 1:
                base = idxs[0]
                for i in idxs[1:]:
                    pair = frozenset({ids[base], ids[i]})
                    if pair in excluded_pairs:
                        continue
                    uf.union(base, i)

    groups = defaultdict(list)
    for i, r in enumerate(records):
        groups[uf.find(i)].append(r)

    return [g for g in groups.values() if len(g) > 1]


def _completeness_score(r, fields):
    return sum(1 for f in fields if r.get(f))


def choose_primary(group, fields):
    """Sceglie il record 'principale' del gruppo: quello con più campi compilati,
    a parità sceglie il più vecchio (created_at minore)."""
    def sort_key(r):
        return (-_completeness_score(r, fields), r.get("created_at") or "")
    ordered = sorted(group, key=sort_key)
    return ordered[0], ordered[1:]


def client_match_keys():
    return [
        lambda r: normalize_email(r.get("email")),
        lambda r: normalize_phone(r.get("phone")) or normalize_phone(r.get("whatsapp")),
        lambda r: normalize_name(r.get("name"), r.get("company")),
    ]


def contact_match_keys():
    return [
        lambda r: normalize_email(r.get("email")),
        lambda r: (normalize_phone(r.get("phone")) or normalize_phone(r.get("mobile"))
                   or normalize_phone(r.get("whatsapp"))),
        lambda r: normalize_name(r.get("full_name"), r.get("company")),
    ]


def compute_merge_plan(primary, others, email_field="email", phone_field="phone"):
    """
    Calcola cosa scrivere nei campi secondari e nelle note del record primario,
    raccogliendo i valori di email/telefono DIVERSI trovati negli altri record
    del gruppo, senza mai perderne uno.
    Ritorna un dict: {"secondary_email": ..., "secondary_phone": ..., "extra_notes": [righe]}
    """
    seen_emails = {normalize_email(primary.get(email_field))} - {None}
    seen_phones = {normalize_phone(primary.get(phone_field))} - {None}
    extra_emails, extra_phones, extra_notes = [], [], []

    for o in others:
        e = o.get(email_field)
        ne = normalize_email(e)
        if e and ne not in seen_emails:
            extra_emails.append(e)
            seen_emails.add(ne)
        p = o.get(phone_field)
        npn = normalize_phone(p)
        if p and npn not in seen_phones:
            extra_phones.append(p)
            seen_phones.add(npn)
        if o.get("notes"):
            extra_notes.append(f"[unito da scheda {o.get('id')}] {o.get('notes')}")

    plan = {
        "secondary_email": extra_emails[0] if extra_emails else None,
        "secondary_phone": extra_phones[0] if extra_phones else None,
        "overflow_notes": [],
    }
    # se ci sono più di 2 valori diversi in totale (primario + 1 extra già in
    # campo dedicato), il resto finisce in una nota esplicita, così non si perde nulla
    if len(extra_emails) > 1:
        plan["overflow_notes"].append("Altre email trovate nei doppioni: " + ", ".join(extra_emails[1:]))
    if len(extra_phones) > 1:
        plan["overflow_notes"].append("Altri telefoni trovati nei doppioni: " + ", ".join(extra_phones[1:]))
    plan["overflow_notes"].extend(extra_notes)
    return plan
