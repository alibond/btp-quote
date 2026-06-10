"""
Quotes Service — versione Vercel (serverless)
Fonti supportate:
  - BTP: scraping Borsa Italiana  -> /api/quotes?isin=IT0005634800
  - Allianz Previdenza fondi      -> /api/allianz?linea=LINEA+AZIONARIA
"""

import re
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests as req
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS1 = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",


  
}


HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.allianz.it/servizi/quotazioni-rendimenti.html",
        "Origin": "https://www.allianz.it",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "it-IT,it;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
}



ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

def validate_isin(isin):
    return bool(ISIN_RE.match(isin))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_it_date(text: str) -> str:
    """Converte '03/06/26' o '03/06/2026' in '2026-06-03'."""
    text = text.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Data non riconosciuta: {text}")

def parse_it_price(text: str) -> float:
    """Converte '34,648' in 34.648."""
    return float(text.strip().replace(".", "").replace(",", "."))

# ---------------------------------------------------------------------------
# BTP — scraping Borsa Italiana
# ---------------------------------------------------------------------------

def scrape_btp(isin: str) -> float:
    url = f"https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/scheda/{isin}-MOTX.html?lang=it"
    r = req.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    el = soup.select_one("span.-formatPrice strong")
    if not el:
        raise RuntimeError(f"Prezzo non trovato per {isin}")
    return parse_it_price(el.get_text(strip=True))

# ---------------------------------------------------------------------------
# Allianz — API JSON
# ---------------------------------------------------------------------------

ALLIANZ_URL = "https://ws.allianz.it/WSAllianz/quotazioni-rendimenti/fondiGestioniPrevidenza"

def fetch_allianz(linea: str) -> dict:
    """
    Recupera quotazione di una linea Allianz Previdenza.
    Cerca in tutti i table[].quotations la prima corrispondenza
    con quote[0] == linea (case-insensitive).
    Ritorna { "date": "yyyy-MM-dd", "close": float }
    """
    r = req.get(ALLIANZ_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()

    linea_upper = linea.strip().upper()

    for table in data.get("tables", []):
        for q in table.get("quotations", []):
            quote = q.get("quote", [])
            if not quote:
                continue
            # Il nome del comparto è sempre il primo elemento (stringa)
            name = quote[0] if isinstance(quote[0], str) else quote[0].get("text", "")
            if name.strip().upper() == linea_upper:
                date_str = parse_it_date(quote[1])
                price    = parse_it_price(quote[2])
                return {"date": date_str, "close": price}

    raise RuntimeError(f"Linea non trovata: '{linea}'. "
                       f"Controlla il nome esatto (es. 'LINEA AZIONARIA').")

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return jsonify({
        "service": "Quotes Service",
        "endpoints": {
            "BTP": "/api/quotes?isin=IT0005634800",
            "Allianz": "/api/allianz?linea=LINEA+AZIONARIA",
        },
        "pp_config_btp": {
            "provider": "JSON Quote Feed",
            "path_to_date": "$[*].date",
            "path_to_close": "$[*].close",
        }
    })


@app.route("/api/quotes")
def quotes():
    """Quotazione corrente BTP da Borsa Italiana."""
    isin = request.args.get("isin", "").strip().upper()
    if not isin:
        return jsonify({"error": "Parametro 'isin' obbligatorio"}), 400
    if not validate_isin(isin):
        return jsonify({"error": f"ISIN non valido: {isin}"}), 400
    try:
        price = scrape_btp(isin)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    from datetime import date
    return jsonify([{"date": date.today().isoformat(), "close": price}])


@app.route("/api/allianz")
def allianz():
    """
    Quotazione corrente di una linea Allianz Previdenza.

    Parametro: linea (nome esatto del comparto)
    Esempi:
      /api/allianz?linea=LINEA+AZIONARIA
      /api/allianz?linea=LINEA+FLESSIBILE+GARANZIA+REST.+CAPITALE

    Configurazione Portfolio Performance:
      Provider:      JSON Quote Feed
      Feed URL:      https://<dominio>/api/allianz?linea=LINEA+AZIONARIA
      Path to Date:  $[*].date
      Path to Close: $[*].close
    """
    linea = request.args.get("linea", "").strip()
    if not linea:
        return jsonify({"error": "Parametro 'linea' obbligatorio"}), 400
    try:
        result = fetch_allianz(linea)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    return jsonify([result])
