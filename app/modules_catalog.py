"""Catalogo dei moduli di settore attivabili (Fase 9).

Il catalogo è statico e definito qui in codice (non in tabella DB): aggiungere
un nuovo settore significa aggiungere una riga a MODULE_CATALOG e fare un
redeploy, coerente con l'approccio già usato altrove nel progetto per evitare
di introdurre uno strumento di migrazione (vedi commento in main.py). Quali
moduli sono ATTIVI per un tenant specifico è invece dati vivi, salvati nella
tabella tenant_module_activations (vedi models.py).

Ogni modulo ha un piano minimo (min_plan) per l'autoattivazione da parte del
cliente stesso: free | premium | enterprise. Il super admin può sempre
attivare qualunque modulo per qualunque tenant, a prescindere dal piano
(vedi platform_admin_router.py), così può sbloccare una funzionalità in fase
di trattativa commerciale prima ancora che il cliente faccia l'upgrade."""

PLAN_RANK = {"free": 0, "premium": 1, "enterprise": 2}


def plan_meets_minimum(tenant_plan: str, min_plan: str) -> bool:
    return PLAN_RANK.get(tenant_plan, 0) >= PLAN_RANK.get(min_plan, 0)


MODULE_CATALOG = [
    # --- Salute ---
    {"slug": "studi_medici", "sector_group": "Salute", "min_plan": "premium",
     "name_it": "Studi Medici", "name_en": "Medical Practices"},

    # --- Ingegneria & Tecnico ---
    {"slug": "servizi_ingegneria", "sector_group": "Ingegneria & Tecnico", "min_plan": "premium",
     "name_it": "Servizi di Ingegneria", "name_en": "Engineering Services",
     # Modulo pilota (Fase 9.1) con funzionalità dedicata: vedi engineering_router.py.
     "has_dedicated_feature": True},

    # --- Immobiliare ---
    {"slug": "agenzie_immobiliari", "sector_group": "Immobiliare", "min_plan": "premium",
     "name_it": "Agenzie Immobiliari", "name_en": "Real Estate Agencies",
     "has_dedicated_feature": True},

    # --- Legale & Contabilità ---
    {"slug": "studi_legali", "sector_group": "Legale & Contabilità", "min_plan": "premium",
     "name_it": "Studi Legali", "name_en": "Law Firms"},
    {"slug": "studi_commercialisti", "sector_group": "Legale & Contabilità", "min_plan": "premium",
     "name_it": "Studi Commercialisti", "name_en": "Accounting Firms"},

    # --- Impresa ---
    {"slug": "pmi", "sector_group": "Impresa", "min_plan": "free",
     "name_it": "PMI (Piccole e Medie Imprese)", "name_en": "SMEs"},

    # --- Estrattivo ---
    {"slug": "miniere", "sector_group": "Estrattivo", "min_plan": "enterprise",
     "name_it": "Miniere", "name_en": "Mining"},
    {"slug": "servizi_miniere", "sector_group": "Estrattivo", "min_plan": "enterprise",
     "name_it": "Agenzie di Servizi per Miniere", "name_en": "Mining Services Agencies"},

    # --- Marketing & IT ---
    {"slug": "servizi_marketing", "sector_group": "Marketing & IT", "min_plan": "premium",
     "name_it": "Agenzie di Servizi di Marketing", "name_en": "Marketing Services Agencies",
     "has_dedicated_feature": True},
    {"slug": "servizi_it", "sector_group": "Marketing & IT", "min_plan": "premium",
     "name_it": "Agenzie di Servizi IT", "name_en": "IT Services Agencies",
     "has_dedicated_feature": True},

    # --- Ristorazione & Hospitality ---
    {"slug": "ristorazione", "sector_group": "Ristorazione & Hospitality", "min_plan": "premium",
     "name_it": "Ristoranti, Pizzerie, Kebab, Paninoteche, Pub con Cucina", "name_en": "Restaurants & Food Venues",
     "has_dedicated_feature": True},
    {"slug": "bar_bistrot", "sector_group": "Ristorazione & Hospitality", "min_plan": "premium",
     "name_it": "Bar, Bistrot", "name_en": "Bars & Bistros",
     "has_dedicated_feature": True},
    {"slug": "locali_notturni", "sector_group": "Ristorazione & Hospitality", "min_plan": "premium",
     "name_it": "Pub, Discoteche, Locali Notturni", "name_en": "Pubs, Clubs & Nightlife",
     "has_dedicated_feature": True},
    {"slug": "hotel", "sector_group": "Ristorazione & Hospitality", "min_plan": "enterprise",
     "name_it": "Hotel, Residence, Resort", "name_en": "Hotels & Resorts",
     "has_dedicated_feature": True},

    # --- Cura della persona ---
    {"slug": "barbieri_parrucchieri", "sector_group": "Cura della persona", "min_plan": "premium",
     "name_it": "Barbieri, Parrucchieri", "name_en": "Barbers & Hairdressers"},

    # --- Automotive ---
    {"slug": "autorivenditori", "sector_group": "Automotive", "min_plan": "premium",
     "name_it": "Autorivenditori", "name_en": "Car Dealers"},
    {"slug": "officine", "sector_group": "Automotive", "min_plan": "premium",
     "name_it": "Meccanici, Elettrauti, Idraulici", "name_en": "Repair Shops"},
    {"slug": "concessionarie", "sector_group": "Automotive", "min_plan": "premium",
     "name_it": "Concessionarie (Auto, Barche, Moto)", "name_en": "Dealerships (Cars, Boats, Motorcycles)"},

    # --- Commercio ---
    {"slug": "ecommerce", "sector_group": "Commercio", "min_plan": "free",
     "name_it": "E-commerce", "name_en": "E-commerce"},
    {"slug": "negozi_retail", "sector_group": "Commercio", "min_plan": "free",
     "name_it": "Negozi (Abbigliamento, Scarpe, Cibo, Supermercati, Oggettistica, Casa)", "name_en": "Retail Stores"},

    # --- Viaggi ---
    {"slug": "agenzie_viaggi", "sector_group": "Viaggi", "min_plan": "premium",
     "name_it": "Agenzie di Viaggi", "name_en": "Travel Agencies"},

    # --- Risorse Umane ---
    {"slug": "risorse_umane", "sector_group": "Risorse Umane", "min_plan": "premium",
     "name_it": "Risorse Umane", "name_en": "Human Resources"},
    {"slug": "hr_recruiting", "sector_group": "Risorse Umane", "min_plan": "enterprise",
     "name_it": "HR & Recruiting (CV, assunzioni, costo del lavoro)", "name_en": "HR & Recruiting (CVs, hiring, labor cost)"},

    # --- Servizi ---
    {"slug": "agenzie_servizi", "sector_group": "Servizi", "min_plan": "premium",
     "name_it": "Agenzie di Servizi", "name_en": "Service Agencies"},
    {"slug": "pulizie_manutenzione", "sector_group": "Servizi", "min_plan": "premium",
     "name_it": "Agenzie di Pulizia e Manutenzione", "name_en": "Cleaning & Maintenance Agencies"},

    # --- Sport & Benessere ---
    {"slug": "palestre", "sector_group": "Sport & Benessere", "min_plan": "premium",
     "name_it": "Palestre e Centri Sportivi", "name_en": "Gyms & Sports Centers"},
]

MODULE_BY_SLUG = {m["slug"]: m for m in MODULE_CATALOG}

# Rotta frontend dedicata per i moduli pilota con funzionalità propria (Fase 9.1):
# più moduli/settori affini possono condividere la stessa pagina (es. Marketing e
# IT hanno entrambi "progetti cliente"; i quattro moduli di Ristorazione &
# Hospitality condividono tavoli/prenotazioni). I moduli senza voce qui restano
# "solo etichetta" attivabile, senza una pagina propria (in attesa di sviluppo).
DEDICATED_ROUTES = {
    "servizi_ingegneria": "/engineering",
    "agenzie_immobiliari": "/real-estate",
    "servizi_marketing": "/agency-projects",
    "servizi_it": "/agency-projects",
    "ristorazione": "/hospitality",
    "bar_bistrot": "/hospitality",
    "locali_notturni": "/hospitality",
    "hotel": "/hospitality",
}
