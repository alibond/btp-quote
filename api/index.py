"""
BTP Quotes Service — versione Vercel (serverless)
Nota: Vercel è stateless, quindi i dati non vengono salvati su disco.
Ogni chiamata fa scraping fresco da Borsa Italiana.
"""

import re
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests as req
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

def validate_isin(isin):
    return bool(ISIN_RE.match(isin))

def scrape_current_price(isin: str) -> float:
    url = f"https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/scheda/{isin}-MOTX.html?lang=it"
    r = req.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    el = soup.select_one("span.-formatPrice strong")
    if not el:
        raise RuntimeError(f"Prezzo non trovato per {isin}")
    return float(el.get_text(strip=True).replace(",", "."))

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return jsonify({
        "service": "BTP Quotes Service",
        "usage": "/api/quotes?isin=IT0005634800",
        "pp_config": {
            "provider": "JSON Quote Feed",
            "feed_url": "https://<tuo-dominio>.vercel.app/api/quotes?isin=IT0005634800",
            "path_to_date": "$[*].date",
            "path_to_close": "$[*].close"
        }
    })

@app.route("/api/quotes")
def quotes():
    isin = request.args.get("isin", "").strip().upper()
    if not isin:
        return jsonify({"error": "Parametro 'isin' obbligatorio"}), 400
    if not validate_isin(isin):
        return jsonify({"error": f"ISIN non valido: {isin}"}), 400

    try:
        price = scrape_current_price(isin)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    from datetime import date
    today = date.today().isoformat()

    # Vercel è stateless: restituisce solo la quotazione odierna.
    # Lo storico viene accumulato da Portfolio Performance stesso
    # che salva ogni quotazione ricevuta nel suo database locale.
    return jsonify([{"date": today, "close": price}])
