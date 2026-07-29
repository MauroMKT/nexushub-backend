"""Riconoscimento del paese di una Partita IVA / VAT number.

Le partite IVA europee (per la validazione VIES) hanno il formato
<PREFISSO PAESE 2 lettere><cifre>, es. DE123456789, FR12345678901.
L'Italia è un caso particolare: la Partita IVA nazionale è composta da
11 cifre numeriche SENZA alcun prefisso lettera (il prefisso "IT" si usa
solo nel formato intracomunitario IT-VIES).

Questa utility fa un riconoscimento *di formato*, non una validazione
ufficiale VIES (che richiederebbe una chiamata al servizio VIES della UE):
è sufficiente per precompilare il campo "Paese" in fase di registrazione
e mostrare PEC solo se l'azienda è italiana.
"""
import re

EU_VAT_COUNTRIES = {
    "AT": "Austria", "BE": "Belgio", "BG": "Bulgaria", "CY": "Cipro",
    "CZ": "Repubblica Ceca", "DE": "Germania", "DK": "Danimarca",
    "EE": "Estonia", "ES": "Spagna", "FI": "Finlandia", "FR": "Francia",
    "GR": "Grecia", "HR": "Croazia", "HU": "Ungheria", "IE": "Irlanda",
    "IT": "Italia", "LT": "Lituania", "LU": "Lussemburgo", "LV": "Lettonia",
    "MT": "Malta", "NL": "Paesi Bassi", "PL": "Polonia", "PT": "Portogallo",
    "RO": "Romania", "SE": "Svezia", "SI": "Slovenia", "SK": "Slovacchia",
}

NON_EU_VAT_COUNTRIES = {
    "GB": "Regno Unito", "CH": "Svizzera", "NO": "Norvegia", "US": "Stati Uniti",
}

ALL_VAT_COUNTRIES = {**EU_VAT_COUNTRIES, **NON_EU_VAT_COUNTRIES}


def detect_vat_country(vat_number: str) -> dict:
    """Ritorna {country_code, country_name, is_italian, valid_format} a partire
    da una stringa di partita IVA, senza chiamare servizi esterni."""
    if not vat_number:
        return {"country_code": None, "country_name": None, "is_italian": False, "valid_format": False}

    cleaned = re.sub(r"[\s\-\.]", "", vat_number.strip().upper())

    # Formato UE/estero: 2 lettere + cifre (es. DE123456789, FR12345678901)
    m = re.match(r"^([A-Z]{2})(\d{5,15})$", cleaned)
    if m:
        code = m.group(1)
        if code in ALL_VAT_COUNTRIES:
            return {
                "country_code": code,
                "country_name": ALL_VAT_COUNTRIES[code],
                "is_italian": code == "IT",
                "valid_format": True,
            }
        return {"country_code": code, "country_name": "Sconosciuto", "is_italian": False, "valid_format": False}

    # Formato italiano nazionale: 11 cifre senza prefisso
    if re.match(r"^\d{11}$", cleaned):
        return {"country_code": "IT", "country_name": "Italia", "is_italian": True, "valid_format": True}

    return {"country_code": None, "country_name": None, "is_italian": False, "valid_format": False}
