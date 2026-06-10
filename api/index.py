"""
Quotes Service — versione Vercel (serverless)
Fonti supportate:
  - BTP:    scraping Borsa Italiana  -> /api/quotes?isin=IT0005634800
  - Fondi:  scraping Teleborsa       -> /api/fondo?slug=allianz-previdenza-l-azionaria-alpfra05-RkMuQUxQRlJBMDU
"""

import re
from datetime import datetime, date
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_it_date(text: str) -> str:
    text = text.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Data non riconosciuta: {text}")

def parse_it_price(text: str) -> float:
    # Gestisce sia "34,648" che "1.234,56"
    text = text.strip()
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    return float(text)

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
# Fondi — scraping Teleborsa
# ---------------------------------------------------------------------------

def scrape_teleborsa(slug: str) -> dict:
    """
    Parametro slug: parte finale dell'URL Teleborsa del fondo.
    Es: 'allianz-previdenza-l-azionaria-alpfra05-RkMuQUxQRlJBMDU'
    Ritorna { "date": "yyyy-MM-dd", "close": float }
    """
    url = f"https://www.teleborsa.it/fondi/{slug}"
    r = req.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # Prezzo: id fisso nel DOM di Teleborsa
    el_price = soup.select_one("#ctl00_phContents_ctlHeader_lblPrice")
    if not el_price:
        raise RuntimeError(f"Prezzo non trovato per slug: {slug}")
    price = parse_it_price(el_price.get_text(strip=True))

    # Data: primo <strong> con formato dd/mm/yyyy
    date_str = None
    for tag in soup.find_all(string=re.compile(r'\d{2}/\d{2}/\d{4}')):
        m = re.search(r'(\d{2}/\d{2}/\d{4})', tag)
        if m:
            try:
                date_str = parse_it_date(m.group(1))
                break
            except ValueError:
                continue
    if not date_str:
        date_str = date.today().isoformat()

    return {"date": date_str, "close": price}

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return jsonify({
        "service": "Quotes Service",
        "endpoints": {
            "BTP": "/api/quotes?isin=IT0005634800",
            "Fondo (Teleborsa)": "/api/fondo?slug=allianz-previdenza-l-azionaria-alpfra05-RkMuQUxQRlJBMDU",
        },
        "pp_config": {
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

    return jsonify([{"date": date.today().isoformat(), "close": price}])


@app.route("/api/fondo")
def fondo():
    """
    Quotazione corrente di un fondo da Teleborsa.

    Parametro: slug (parte finale URL Teleborsa)
    Esempi:
      /api/fondo?slug=allianz-previdenza-l-azionaria-alpfra05-RkMuQUxQRlJBMDU
      /api/fondo?slug=allianz-previdenza-l-flessibile-garanzia-rest-capitale-alpfrg01-RkMuQUxQRlJHMDE

    Configurazione Portfolio Performance:
      Provider:      JSON Quote Feed
      Feed URL:      https://<dominio>/api/fondo?slug=<slug>
      Path to Date:  $[*].date
      Path to Close: $[*].close
    """
    slug = request.args.get("slug", "").strip()
    if not slug:
        return jsonify({"error": "Parametro 'slug' obbligatorio"}), 400
    try:
        result = scrape_teleborsa(slug)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    return jsonify([result])
  
