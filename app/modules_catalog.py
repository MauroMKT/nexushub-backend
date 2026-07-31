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

# Le 9 lingue supportate dall'app (vedi frontend/src/locales/*.json). Usate qui
# per validare che ogni modulo/etichetta abbia una traduzione in tutte le lingue,
# non solo it/en come nella prima versione del catalogo (Fase 9.1/9.3) — quel
# gap era esattamente il problema segnalato: sidebar tradotta ma nomi modulo,
# gruppi di settore ed etichette dei record che ricadevano su EN per le altre
# 7 lingue (FR/DE/ES/ZH/JA/RU/AR).
SUPPORTED_LANGS = ["it", "en", "fr", "de", "es", "zh", "ja", "ru", "ar"]

PLAN_RANK = {"free": 0, "premium": 1, "enterprise": 2}


def plan_meets_minimum(tenant_plan: str, min_plan: str) -> bool:
    return PLAN_RANK.get(tenant_plan, 0) >= PLAN_RANK.get(min_plan, 0)


MODULE_CATALOG = [
    # --- Salute ---
    {"slug": "studi_medici", "sector_group": "Salute", "min_plan": "premium",
     "name_it": "Studi Medici", "name_en": "Medical Practices",
     # Fase 9.3: funzionalità dedicata "generica" via sector_records_router.py
     # (un'unica tabella parametrizzata, non uno schema bespoke come i 4 moduli
     # pilota di Fase 9.1) — vedi SectorRecord in models.py.
     "has_dedicated_feature": True,
     "record_label_it": "Pratica Paziente", "record_label_en": "Patient Case"},

    # --- Ingegneria & Tecnico ---
    {"slug": "servizi_ingegneria", "sector_group": "Ingegneria & Tecnico", "min_plan": "premium",
     "name_it": "Servizi di Ingegneria", "name_en": "Engineering Services",
     # Modulo pilota (Fase 9.1) con funzionalità dedicata bespoke: vedi engineering_router.py.
     "has_dedicated_feature": True},

    # --- Immobiliare ---
    {"slug": "agenzie_immobiliari", "sector_group": "Immobiliare", "min_plan": "premium",
     "name_it": "Agenzie Immobiliari", "name_en": "Real Estate Agencies",
     "has_dedicated_feature": True},

    # --- Legale & Contabilità ---
    {"slug": "studi_legali", "sector_group": "Legale & Contabilità", "min_plan": "premium",
     "name_it": "Studi Legali", "name_en": "Law Firms",
     "has_dedicated_feature": True,
     "record_label_it": "Pratica Legale", "record_label_en": "Legal Case"},
    {"slug": "studi_commercialisti", "sector_group": "Legale & Contabilità", "min_plan": "premium",
     "name_it": "Studi Commercialisti", "name_en": "Accounting Firms",
     "has_dedicated_feature": True,
     "record_label_it": "Pratica Contabile", "record_label_en": "Accounting Case"},

    # --- Impresa ---
    {"slug": "pmi", "sector_group": "Impresa", "min_plan": "free",
     "name_it": "PMI (Piccole e Medie Imprese)", "name_en": "SMEs",
     "has_dedicated_feature": True,
     "record_label_it": "Progetto Aziendale", "record_label_en": "Business Project"},

    # --- Estrattivo ---
    {"slug": "miniere", "sector_group": "Estrattivo", "min_plan": "enterprise",
     "name_it": "Miniere", "name_en": "Mining",
     "has_dedicated_feature": True,
     "record_label_it": "Sito Estrattivo", "record_label_en": "Mining Site"},
    {"slug": "servizi_miniere", "sector_group": "Estrattivo", "min_plan": "enterprise",
     "name_it": "Agenzie di Servizi per Miniere", "name_en": "Mining Services Agencies",
     "has_dedicated_feature": True,
     "record_label_it": "Commessa di Servizio", "record_label_en": "Service Contract"},

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
     "name_it": "Barbieri, Parrucchieri", "name_en": "Barbers & Hairdressers",
     "has_dedicated_feature": True,
     "record_label_it": "Trattamento", "record_label_en": "Treatment"},

    # --- Automotive ---
    {"slug": "autorivenditori", "sector_group": "Automotive", "min_plan": "premium",
     "name_it": "Autorivenditori", "name_en": "Car Dealers",
     "has_dedicated_feature": True,
     "record_label_it": "Veicolo in Vendita", "record_label_en": "Vehicle Listing"},
    {"slug": "officine", "sector_group": "Automotive", "min_plan": "premium",
     "name_it": "Meccanici, Elettrauti, Idraulici", "name_en": "Repair Shops",
     "has_dedicated_feature": True,
     "record_label_it": "Intervento in Officina", "record_label_en": "Repair Job"},
    {"slug": "concessionarie", "sector_group": "Automotive", "min_plan": "premium",
     "name_it": "Concessionarie (Auto, Barche, Moto)", "name_en": "Dealerships (Cars, Boats, Motorcycles)",
     "has_dedicated_feature": True,
     "record_label_it": "Trattativa Veicolo", "record_label_en": "Vehicle Deal"},

    # --- Commercio ---
    {"slug": "ecommerce", "sector_group": "Commercio", "min_plan": "free",
     "name_it": "E-commerce", "name_en": "E-commerce",
     "has_dedicated_feature": True,
     "record_label_it": "Ordine", "record_label_en": "Order"},
    {"slug": "negozi_retail", "sector_group": "Commercio", "min_plan": "free",
     "name_it": "Negozi (Abbigliamento, Scarpe, Cibo, Supermercati, Oggettistica, Casa)", "name_en": "Retail Stores",
     "has_dedicated_feature": True,
     "record_label_it": "Ordine Cliente", "record_label_en": "Customer Order"},

    # --- Viaggi ---
    {"slug": "agenzie_viaggi", "sector_group": "Viaggi", "min_plan": "premium",
     "name_it": "Agenzie di Viaggi", "name_en": "Travel Agencies",
     "has_dedicated_feature": True,
     "record_label_it": "Pratica Viaggio", "record_label_en": "Travel Booking"},

    # --- Risorse Umane ---
    {"slug": "risorse_umane", "sector_group": "Risorse Umane", "min_plan": "premium",
     "name_it": "Risorse Umane", "name_en": "Human Resources",
     "has_dedicated_feature": True,
     "record_label_it": "Pratica HR", "record_label_en": "HR Case"},
    {"slug": "hr_recruiting", "sector_group": "Risorse Umane", "min_plan": "enterprise",
     "name_it": "HR & Recruiting (CV, assunzioni, costo del lavoro)", "name_en": "HR & Recruiting (CVs, hiring, labor cost)",
     "has_dedicated_feature": True,
     "record_label_it": "Candidatura", "record_label_en": "Candidate Application"},

    # --- Servizi ---
    {"slug": "agenzie_servizi", "sector_group": "Servizi", "min_plan": "premium",
     "name_it": "Agenzie di Servizi", "name_en": "Service Agencies",
     "has_dedicated_feature": True,
     "record_label_it": "Commessa di Servizio", "record_label_en": "Service Job"},
    {"slug": "pulizie_manutenzione", "sector_group": "Servizi", "min_plan": "premium",
     "name_it": "Agenzie di Pulizia e Manutenzione", "name_en": "Cleaning & Maintenance Agencies",
     "has_dedicated_feature": True,
     "record_label_it": "Intervento di Pulizia", "record_label_en": "Cleaning Job"},

    # --- Sport & Benessere ---
    {"slug": "palestre", "sector_group": "Sport & Benessere", "min_plan": "premium",
     "name_it": "Palestre e Centri Sportivi", "name_en": "Gyms & Sports Centers",
     "has_dedicated_feature": True,
     "record_label_it": "Abbonamento", "record_label_en": "Membership"},
]

# ---------------------------------------------------------------------------
# Fase 9.4 — traduzioni complete in 9 lingue.
#
# La Fase 9.1/9.3 aveva introdotto name_it/name_en e record_label_it/en per
# ogni modulo, con un fallback "usa l'inglese" per le altre 7 lingue dell'app
# (FR/DE/ES/ZH/JA/RU/AR) — un compromesso esplicito, ma di fatto un buco di
# traduzione: la sidebar mostrava l'etichetta tradotta per le 4 pagine pilota
# bespoke, ma i NOMI DEI MODULI, i GRUPPI DI SETTORE e le ETICHETTE DEI RECORD
# restavano in inglese per chiunque non usasse IT/EN.
#
# Qui sotto le traduzioni mancanti, tenute separate dal blocco sopra (invece di
# infilare altri 7 campi in ognuna delle 26 righe) per restare leggibili e
# verificabili modulo per modulo. Il merge avviene subito dopo, in un unico
# posto, così un domani una nuova lingua si aggiunge qui e non in 26 punti.
# ---------------------------------------------------------------------------

MODULE_NAME_I18N = {
    "studi_medici": {
        "fr": "Cabinets Médicaux", "de": "Arztpraxen", "es": "Consultorios Médicos",
        "zh": "医疗诊所", "ja": "医療クリニック", "ru": "Медицинские практики", "ar": "العيادات الطبية",
    },
    "servizi_ingegneria": {
        "fr": "Services d'Ingénierie", "de": "Ingenieurdienstleistungen", "es": "Servicios de Ingeniería",
        "zh": "工程服务", "ja": "エンジニアリングサービス", "ru": "Инженерные услуги", "ar": "الخدمات الهندسية",
    },
    "agenzie_immobiliari": {
        "fr": "Agences Immobilières", "de": "Immobilienagenturen", "es": "Agencias Inmobiliarias",
        "zh": "房地产中介", "ja": "不動産仲介業", "ru": "Агентства недвижимости", "ar": "وكالات العقارات",
    },
    "studi_legali": {
        "fr": "Cabinets d'Avocats", "de": "Anwaltskanzleien", "es": "Bufetes de Abogados",
        "zh": "律师事务所", "ja": "法律事務所", "ru": "Юридические фирмы", "ar": "مكاتب المحاماة",
    },
    "studi_commercialisti": {
        "fr": "Cabinets d'Expertise Comptable", "de": "Steuerberatungskanzleien", "es": "Despachos de Contabilidad",
        "zh": "会计师事务所", "ja": "会計事務所", "ru": "Бухгалтерские фирмы", "ar": "مكاتب المحاسبة",
    },
    "pmi": {
        "fr": "PME (Petites et Moyennes Entreprises)", "de": "KMU (Kleine und mittlere Unternehmen)",
        "es": "PYMES (Pequeñas y Medianas Empresas)", "zh": "中小企业", "ja": "中小企業",
        "ru": "МСП (Малые и средние предприятия)", "ar": "الشركات الصغيرة والمتوسطة",
    },
    "miniere": {
        "fr": "Mines", "de": "Bergwerke", "es": "Minería",
        "zh": "矿业", "ja": "鉱業", "ru": "Горнодобывающие предприятия", "ar": "التعدين",
    },
    "servizi_miniere": {
        "fr": "Agences de Services Miniers", "de": "Dienstleister für Bergbauunternehmen",
        "es": "Agencias de Servicios Mineros", "zh": "矿业服务机构", "ja": "鉱業サービス業者",
        "ru": "Агентства горнодобывающих услуг", "ar": "وكالات خدمات التعدين",
    },
    "servizi_marketing": {
        "fr": "Agences de Services Marketing", "de": "Marketingdienstleister",
        "es": "Agencias de Servicios de Marketing", "zh": "市场营销服务机构", "ja": "マーケティングサービス代理店",
        "ru": "Маркетинговые агентства", "ar": "وكالات خدمات التسويق",
    },
    "servizi_it": {
        "fr": "Agences de Services Informatiques", "de": "IT-Dienstleister", "es": "Agencias de Servicios de TI",
        "zh": "IT服务机构", "ja": "ITサービス代理店", "ru": "IT-агентства", "ar": "وكالات خدمات تقنية المعلومات",
    },
    "ristorazione": {
        "fr": "Restaurants, Pizzerias, Kebabs, Sandwicheries, Pubs avec Cuisine",
        "de": "Restaurants, Pizzerien, Kebabläden, Sandwich-Bars, Gastro-Pubs",
        "es": "Restaurantes, Pizzerías, Kebabs, Bocadillerías, Pubs con Cocina",
        "zh": "餐厅、披萨店、烤肉店、三明治店、供餐酒吧",
        "ja": "レストラン、ピザ店、ケバブ店、サンドイッチ店、食事提供パブ",
        "ru": "Рестораны, пиццерии, кебабные, сэндвич-бары, пабы с кухней",
        "ar": "المطاعم والبيتزاريات ومحلات الكباب والسندويشات والحانات ذات المطبخ",
    },
    "bar_bistrot": {
        "fr": "Bars, Bistrots", "de": "Bars, Bistros", "es": "Bares, Bistrós",
        "zh": "酒吧与小酒馆", "ja": "バー、ビストロ", "ru": "Бары, бистро", "ar": "البارات والمطاعم الصغيرة",
    },
    "locali_notturni": {
        "fr": "Pubs, Discothèques, Vie Nocturne", "de": "Pubs, Diskotheken, Nachtleben",
        "es": "Pubs, Discotecas, Vida Nocturna", "zh": "酒吧、夜店与夜生活场所",
        "ja": "パブ、クラブ、ナイトライフ", "ru": "Пабы, дискотеки, ночные заведения",
        "ar": "الحانات والملاهي الليلية والحياة الليلية",
    },
    "hotel": {
        "fr": "Hôtels, Résidences, Resorts", "de": "Hotels, Residenzen, Resorts", "es": "Hoteles, Residencias, Resorts",
        "zh": "酒店、公寓式旅馆与度假村", "ja": "ホテル、レジデンス、リゾート", "ru": "Отели, резиденции, курорты",
        "ar": "الفنادق والمجمعات السكنية والمنتجعات",
    },
    "barbieri_parrucchieri": {
        "fr": "Barbiers, Coiffeurs", "de": "Barbiere, Friseure", "es": "Barberías, Peluquerías",
        "zh": "理发店与美发沙龙", "ja": "理容室・美容室", "ru": "Барбершопы, парикмахерские",
        "ar": "الحلاقون ومصففو الشعر",
    },
    "autorivenditori": {
        "fr": "Vendeurs Automobiles", "de": "Autohändler", "es": "Vendedores de Coches",
        "zh": "汽车经销商", "ja": "自動車販売店", "ru": "Автосалоны", "ar": "بائعو السيارات",
    },
    "officine": {
        "fr": "Mécaniciens, Électriciens Auto, Plombiers", "de": "Kfz-Mechaniker, Kfz-Elektriker, Klempner",
        "es": "Mecánicos, Electricistas del Automóvil, Fontaneros", "zh": "机修工、汽车电工与水管工",
        "ja": "自動車整備士、自動車電装技師、配管工", "ru": "Автомеханики, автоэлектрики, сантехники",
        "ar": "الميكانيكيون وكهربائيو السيارات والسباكون",
    },
    "concessionarie": {
        "fr": "Concessionnaires (Voitures, Bateaux, Motos)", "de": "Vertragshändler (Autos, Boote, Motorräder)",
        "es": "Concesionarios (Coches, Barcos, Motos)", "zh": "经销商（汽车、船舶、摩托车）",
        "ja": "販売代理店（自動車・ボート・オートバイ）", "ru": "Дилерские центры (автомобили, лодки, мотоциклы)",
        "ar": "الوكالات (سيارات وقوارب ودراجات نارية)",
    },
    "ecommerce": {
        "fr": "E-commerce", "de": "E-Commerce", "es": "Comercio Electrónico",
        "zh": "电子商务", "ja": "Eコマース", "ru": "Электронная коммерция", "ar": "التجارة الإلكترونية",
    },
    "negozi_retail": {
        "fr": "Magasins (Vêtements, Chaussures, Alimentation, Supermarchés, Articles Divers, Maison)",
        "de": "Geschäfte (Kleidung, Schuhe, Lebensmittel, Supermärkte, Geschenkartikel, Haushalt)",
        "es": "Tiendas (Ropa, Calzado, Alimentación, Supermercados, Artículos Varios, Hogar)",
        "zh": "商店（服装、鞋类、食品、超市、礼品、家居）",
        "ja": "店舗（衣料品、靴、食品、スーパー、雑貨、家庭用品）",
        "ru": "Магазины (одежда, обувь, продукты, супермаркеты, товары для дома)",
        "ar": "المتاجر (ملابس وأحذية وأغذية وسوبرماركت وهدايا ومنزل)",
    },
    "agenzie_viaggi": {
        "fr": "Agences de Voyages", "de": "Reisebüros", "es": "Agencias de Viajes",
        "zh": "旅行社", "ja": "旅行代理店", "ru": "Туристические агентства", "ar": "وكالات السفر",
    },
    "risorse_umane": {
        "fr": "Ressources Humaines", "de": "Personalwesen", "es": "Recursos Humanos",
        "zh": "人力资源", "ja": "人事部門", "ru": "Отдел кадров", "ar": "الموارد البشرية",
    },
    "hr_recruiting": {
        "fr": "RH & Recrutement (CV, embauches, coût du travail)",
        "de": "HR & Recruiting (Lebensläufe, Einstellungen, Personalkosten)",
        "es": "RRHH y Selección (CVs, contrataciones, coste laboral)",
        "zh": "人力资源与招聘（简历、招聘、人力成本）",
        "ja": "人事・採用（履歴書、採用、人件費）",
        "ru": "HR и подбор персонала (резюме, найм, стоимость труда)",
        "ar": "الموارد البشرية والتوظيف (السير الذاتية، التوظيف، تكلفة العمالة)",
    },
    "agenzie_servizi": {
        "fr": "Agences de Services", "de": "Dienstleistungsagenturen", "es": "Agencias de Servicios",
        "zh": "服务机构", "ja": "サービス代理店", "ru": "Сервисные агентства", "ar": "وكالات الخدمات",
    },
    "pulizie_manutenzione": {
        "fr": "Agences de Nettoyage et d'Entretien", "de": "Reinigungs- und Wartungsunternehmen",
        "es": "Agencias de Limpieza y Mantenimiento", "zh": "清洁与维护服务机构",
        "ja": "清掃・メンテナンス業者", "ru": "Клининговые и обслуживающие компании",
        "ar": "وكالات التنظيف والصيانة",
    },
    "palestre": {
        "fr": "Salles de Sport et Centres Sportifs", "de": "Fitnessstudios und Sportzentren",
        "es": "Gimnasios y Centros Deportivos", "zh": "健身房与体育中心",
        "ja": "ジム・スポーツセンター", "ru": "Спортзалы и спортивные центры",
        "ar": "الصالات الرياضية والمراكز الرياضية",
    },
}

# Solo per i moduli "generici" di Fase 9.3 (quelli con record_label_it/en).
MODULE_RECORD_LABEL_I18N = {
    "studi_medici": {
        "fr": "Dossier Patient", "de": "Patientenakte", "es": "Caso del Paciente",
        "zh": "患者病历", "ja": "患者ケース", "ru": "Дело пациента", "ar": "ملف المريض",
    },
    "studi_legali": {
        "fr": "Dossier Juridique", "de": "Rechtsfall", "es": "Caso Legal",
        "zh": "法律案件", "ja": "法律案件", "ru": "Юридическое дело", "ar": "القضية القانونية",
    },
    "studi_commercialisti": {
        "fr": "Dossier Comptable", "de": "Buchhaltungsfall", "es": "Caso Contable",
        "zh": "会计事项", "ja": "会計案件", "ru": "Бухгалтерское дело", "ar": "الملف المحاسبي",
    },
    "pmi": {
        "fr": "Projet d'Entreprise", "de": "Unternehmensprojekt", "es": "Proyecto Empresarial",
        "zh": "企业项目", "ja": "事業プロジェクト", "ru": "Бизнес-проект", "ar": "مشروع الأعمال",
    },
    "miniere": {
        "fr": "Site Minier", "de": "Bergbaustandort", "es": "Sitio Minero",
        "zh": "矿场", "ja": "採掘現場", "ru": "Горный участок", "ar": "موقع التعدين",
    },
    "servizi_miniere": {
        "fr": "Contrat de Service", "de": "Dienstleistungsauftrag", "es": "Contrato de Servicio",
        "zh": "服务合同", "ja": "サービス契約", "ru": "Договор на оказание услуг", "ar": "عقد الخدمة",
    },
    "barbieri_parrucchieri": {
        "fr": "Prestation", "de": "Behandlung", "es": "Tratamiento",
        "zh": "服务项目", "ja": "施術", "ru": "Процедура", "ar": "الخدمة",
    },
    "autorivenditori": {
        "fr": "Véhicule à Vendre", "de": "Fahrzeugangebot", "es": "Vehículo en Venta",
        "zh": "待售车辆", "ja": "販売車両", "ru": "Автомобиль на продажу", "ar": "مركبة معروضة للبيع",
    },
    "officine": {
        "fr": "Intervention en Atelier", "de": "Werkstattauftrag", "es": "Intervención en Taller",
        "zh": "维修工单", "ja": "整備作業", "ru": "Ремонтная работа", "ar": "عملية إصلاح",
    },
    "concessionarie": {
        "fr": "Négociation Véhicule", "de": "Fahrzeuggeschäft", "es": "Negociación de Vehículo",
        "zh": "车辆交易", "ja": "車両商談", "ru": "Сделка по автомобилю", "ar": "صفقة مركبة",
    },
    "ecommerce": {
        "fr": "Commande", "de": "Bestellung", "es": "Pedido",
        "zh": "订单", "ja": "注文", "ru": "Заказ", "ar": "الطلب",
    },
    "negozi_retail": {
        "fr": "Commande Client", "de": "Kundenbestellung", "es": "Pedido de Cliente",
        "zh": "客户订单", "ja": "顧客注文", "ru": "Заказ клиента", "ar": "طلب العميل",
    },
    "agenzie_viaggi": {
        "fr": "Dossier de Voyage", "de": "Reisebuchung", "es": "Reserva de Viaje",
        "zh": "旅行预订", "ja": "旅行手配", "ru": "Бронирование поездки", "ar": "حجز السفر",
    },
    "risorse_umane": {
        "fr": "Dossier RH", "de": "HR-Fall", "es": "Caso de RRHH",
        "zh": "人力资源事项", "ja": "人事案件", "ru": "Кадровое дело", "ar": "ملف الموارد البشرية",
    },
    "hr_recruiting": {
        "fr": "Candidature", "de": "Bewerbung", "es": "Candidatura",
        "zh": "求职申请", "ja": "応募", "ru": "Заявка кандидата", "ar": "طلب توظيف",
    },
    "agenzie_servizi": {
        "fr": "Mission de Service", "de": "Serviceauftrag", "es": "Encargo de Servicio",
        "zh": "服务任务", "ja": "サービス業務", "ru": "Сервисное задание", "ar": "مهمة خدمة",
    },
    "pulizie_manutenzione": {
        "fr": "Intervention de Nettoyage", "de": "Reinigungsauftrag", "es": "Trabajo de Limpieza",
        "zh": "清洁工单", "ja": "清掃作業", "ru": "Работа по уборке", "ar": "عملية تنظيف",
    },
    "palestre": {
        "fr": "Abonnement", "de": "Mitgliedschaft", "es": "Membresía",
        "zh": "会员资格", "ja": "会員登録", "ru": "Абонемент", "ar": "العضوية",
    },
}

# Le 15 macro-categorie ("sector_group") mostrate come intestazione di gruppo
# in Impostazioni > Moduli e nel menu "Settore" della registrazione. Chiave =
# valore italiano già presente in sector_group sopra (stabile, usato anche per
# raggruppare), valore = traduzione nelle 9 lingue.
SECTOR_GROUP_I18N = {
    "Salute": {
        "it": "Salute", "en": "Health", "fr": "Santé", "de": "Gesundheit", "es": "Salud",
        "zh": "医疗健康", "ja": "医療", "ru": "Здравоохранение", "ar": "الصحة",
    },
    "Ingegneria & Tecnico": {
        "it": "Ingegneria & Tecnico", "en": "Engineering & Technical", "fr": "Ingénierie & Technique",
        "de": "Ingenieurwesen & Technik", "es": "Ingeniería y Técnica", "zh": "工程与技术",
        "ja": "エンジニアリング・技術", "ru": "Инжиниринг и технологии", "ar": "الهندسة والفنيات",
    },
    "Immobiliare": {
        "it": "Immobiliare", "en": "Real Estate", "fr": "Immobilier", "de": "Immobilien",
        "es": "Inmobiliario", "zh": "房地产", "ja": "不動産", "ru": "Недвижимость", "ar": "العقارات",
    },
    "Legale & Contabilità": {
        "it": "Legale & Contabilità", "en": "Legal & Accounting", "fr": "Juridique & Comptabilité",
        "de": "Recht & Buchhaltung", "es": "Legal y Contabilidad", "zh": "法律与会计",
        "ja": "法務・会計", "ru": "Юриспруденция и бухгалтерия", "ar": "القانون والمحاسبة",
    },
    "Impresa": {
        "it": "Impresa", "en": "Business", "fr": "Entreprise", "de": "Unternehmen", "es": "Empresa",
        "zh": "企业", "ja": "企業", "ru": "Бизнес", "ar": "الأعمال",
    },
    "Estrattivo": {
        "it": "Estrattivo", "en": "Extractive Industry", "fr": "Extraction minière", "de": "Bergbau",
        "es": "Extractivo", "zh": "采矿业", "ja": "採掘業", "ru": "Добывающая промышленность",
        "ar": "الصناعات الاستخراجية",
    },
    "Marketing & IT": {
        "it": "Marketing & IT", "en": "Marketing & IT", "fr": "Marketing & Informatique",
        "de": "Marketing & IT", "es": "Marketing e IT", "zh": "市场营销与IT",
        "ja": "マーケティング・IT", "ru": "Маркетинг и ИТ", "ar": "التسويق وتقنية المعلومات",
    },
    "Ristorazione & Hospitality": {
        "it": "Ristorazione & Hospitality", "en": "Food Service & Hospitality",
        "fr": "Restauration & Hôtellerie", "de": "Gastronomie & Hotellerie",
        "es": "Restauración y Hostelería", "zh": "餐饮与酒店业", "ja": "飲食・宿泊業",
        "ru": "Общественное питание и гостиничный бизнес", "ar": "المطاعم والضيافة",
    },
    "Cura della persona": {
        "it": "Cura della persona", "en": "Personal Care", "fr": "Soins de la personne",
        "de": "Körperpflege", "es": "Cuidado personal", "zh": "个人护理",
        "ja": "パーソナルケア", "ru": "Личный уход", "ar": "العناية الشخصية",
    },
    "Automotive": {
        "it": "Automotive", "en": "Automotive", "fr": "Automobile", "de": "Automobilbranche",
        "es": "Automoción", "zh": "汽车行业", "ja": "自動車業界", "ru": "Автомобильная отрасль",
        "ar": "صناعة السيارات",
    },
    "Commercio": {
        "it": "Commercio", "en": "Retail & Commerce", "fr": "Commerce", "de": "Handel",
        "es": "Comercio", "zh": "商业零售", "ja": "商業・小売", "ru": "Торговля", "ar": "التجارة",
    },
    "Viaggi": {
        "it": "Viaggi", "en": "Travel", "fr": "Voyages", "de": "Reisen", "es": "Viajes",
        "zh": "旅游", "ja": "旅行", "ru": "Путешествия", "ar": "السفر",
    },
    "Risorse Umane": {
        "it": "Risorse Umane", "en": "Human Resources", "fr": "Ressources Humaines",
        "de": "Personalwesen", "es": "Recursos Humanos", "zh": "人力资源",
        "ja": "人事", "ru": "Кадры (HR)", "ar": "الموارد البشرية",
    },
    "Servizi": {
        "it": "Servizi", "en": "Services", "fr": "Services", "de": "Dienstleistungen",
        "es": "Servicios", "zh": "服务业", "ja": "サービス業", "ru": "Услуги", "ar": "الخدمات",
    },
    "Sport & Benessere": {
        "it": "Sport & Benessere", "en": "Sport & Wellness", "fr": "Sport & Bien-être",
        "de": "Sport & Wellness", "es": "Deporte y Bienestar", "zh": "运动与健康",
        "ja": "スポーツ・ウェルネス", "ru": "Спорт и оздоровление", "ar": "الرياضة واللياقة",
    },
}

# Merge: applica le traduzioni sopra direttamente sui dict di MODULE_CATALOG,
# così il resto del codice (schemas.py, modules_router.py) può continuare a
# leggere semplicemente m["name_xx"] / m["record_label_xx"] senza sapere nulla
# di questo meccanismo. Un solo punto in cui può "rompersi" se manca una lingua.
for _m in MODULE_CATALOG:
    _m.update({f"name_{_lang}": _val for _lang, _val in MODULE_NAME_I18N.get(_m["slug"], {}).items()})
    if _m["slug"] in MODULE_RECORD_LABEL_I18N:
        _m.update({f"record_label_{_lang}": _val for _lang, _val in MODULE_RECORD_LABEL_I18N[_m["slug"]].items()})

# Verifica di integrità a import-time: se manca una traduzione per un modulo o
# un gruppo, meglio un errore rumoroso subito (in fase di avvio/deploy) che un
# fallback silenzioso su un'altra lingua scoperto mesi dopo da un cliente.
for _m in MODULE_CATALOG:
    for _lang in SUPPORTED_LANGS:
        if not _m.get(f"name_{_lang}"):
            raise RuntimeError(f"modules_catalog: manca name_{_lang} per il modulo '{_m['slug']}'")
        if _m.get("record_label_it") and not _m.get(f"record_label_{_lang}"):
            raise RuntimeError(f"modules_catalog: manca record_label_{_lang} per il modulo '{_m['slug']}'")
    if _m["sector_group"] not in SECTOR_GROUP_I18N:
        raise RuntimeError(f"modules_catalog: manca la traduzione del sector_group '{_m['sector_group']}'")

MODULE_BY_SLUG = {m["slug"]: m for m in MODULE_CATALOG}


def sector_group_names(sector_group: str) -> dict:
    """Ritorna il dict {lingua: etichetta} per il gruppo di settore indicato,
    con fallback sul valore italiano grezzo se per qualche motivo non fosse
    nella mappa (non dovrebbe succedere, vedi verifica di integrità sopra)."""
    return SECTOR_GROUP_I18N.get(sector_group, {lang: sector_group for lang in SUPPORTED_LANGS})


def i18n_kwargs(m: dict) -> dict:
    """Kwargs pronti da spargere (**) nei costruttori di ModuleCatalogItem /
    ModulePublicCatalogItem: name_xx, record_label_xx e sector_group_xx per
    tutte le lingue diverse da it/en (già presenti come campi obbligatori a
    parte). Un solo punto per costruire questi campi evita di ripeterli in
    ogni router che assembla il catalogo (modules_router.py, platform_admin_router.py)."""
    kwargs = {}
    group_names = sector_group_names(m["sector_group"])
    for lang in SUPPORTED_LANGS:
        if lang in ("it", "en"):
            continue
        kwargs[f"name_{lang}"] = m.get(f"name_{lang}")
        kwargs[f"record_label_{lang}"] = m.get(f"record_label_{lang}")
    for lang in SUPPORTED_LANGS:
        kwargs[f"sector_group_{lang}"] = group_names.get(lang)
    return kwargs


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

# Fase 9.3: i restanti settori del catalogo (senza uno schema dati bespoke come
# i 4 moduli pilota sopra) condividono un'unica pagina generica parametrizzata
# per slug — /sector/<slug> — che usa la tabella SectorRecord e i "record_label"
# definiti sopra in MODULE_CATALOG per mostrare un'etichetta pertinente al
# settore (es. "Pratica Legale" invece di un generico "Elemento").
GENERIC_SECTOR_SLUGS = [
    m["slug"] for m in MODULE_CATALOG
    if m.get("has_dedicated_feature") and m["slug"] not in DEDICATED_ROUTES
]
for _slug in GENERIC_SECTOR_SLUGS:
    DEDICATED_ROUTES[_slug] = f"/sector/{_slug}"
