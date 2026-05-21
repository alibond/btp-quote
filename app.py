"""
BTP Quotes Service
Webservice che recupera le quotazioni storiche dei BTP da Borsa Italiana
e le pubblica in formato JSON compatibile con Portfolio Performance.

Endpoint:
  GET /quotes?isin=IT0005634800
  GET /quotes?isin=IT0005634800&from=2024-01-01&to=2024-12-31
  GET /health
  GET /                  → pagina di documentazione
"""

import os
import re
import time
import logging
from datetime import datetime, timedelta
from functools import lru_cache

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # permette a PP di chiamare il servizio

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9",
}

BORSA_ITALIANA_URL = (
    "https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/"
    "listino-ufficiale.html?isin={isin}&mic=MOTX&lang=it"
)

# Cache semplice in memoria: { isin: (timestamp, [quotes]) }
_cache: dict = {}
CACHE_TTL_SECONDS = 3600  # 1 ora


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _fetch_html(url: str) -> str:
    """Scarica la pagina con retry semplice."""
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            log.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Impossibile recuperare dati da: {url}")


def _parse_price(text: str) -> float | None:
    """Converte '101,03' o '101.03' in float."""
    text = text.strip().replace("\xa0", "").replace(" ", "")
    # Formato italiano: punto come separatore migliaia, virgola come decimale
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(text: str) -> str | None:
    """Converte '25/02/26' o '25/02/2026' in 'yyyy-MM-dd'."""
    text = text.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fetch_quotes_borsa_italiana(isin: str) -> list[dict]:
    """
    Scrape del listino ufficiale di Borsa Italiana per un BTP.
    Restituisce lista di { "date": "yyyy-MM-dd", "close": float }
    ordinata per data crescente.
    """
    url = BORSA_ITALIANA_URL.format(isin=isin.upper())
    log.info("Fetching: %s", url)
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    quotes = []

    # La tabella ha class "m-table" su Borsa Italiana
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 2:
                continue

            # Cerca colonne data e prezzo — il listino ufficiale ha:
            # Data | Prezzo Ufficiale | ... 
            date_str = _parse_date(cols[0])
            if not date_str:
                continue

            # Il prezzo ufficiale è in genere la seconda colonna
            price = None
            for col in cols[1:4]:
                price = _parse_price(col)
                if price and 50 < price < 200:  # sanity check per BTP
                    break

            if date_str and price:
                quotes.append({"date": date_str, "close": price})

    # Rimuovi duplicati e ordina per data
    seen = set()
    unique = []
    for q in quotes:
        if q["date"] not in seen:
            seen.add(q["date"])
            unique.append(q)

    unique.sort(key=lambda x: x["date"])
    log.info("Parsed %d quotes for %s", len(unique), isin)
    return unique


def get_quotes_cached(isin: str) -> list[dict]:
    """Wrapper con cache in memoria."""
    now = time.time()
    if isin in _cache:
        ts, data = _cache[isin]
        if now - ts < CACHE_TTL_SECONDS:
            log.info("Cache hit for %s (%d quotes)", isin, len(data))
            return data

    data = fetch_quotes_borsa_italiana(isin)
    _cache[isin] = (now, data)
    return data


# ---------------------------------------------------------------------------
# Validazione ISIN
# ---------------------------------------------------------------------------

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

def validate_isin(isin: str) -> bool:
    return bool(ISIN_RE.match(isin.upper()))


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@app.route("/quotes")
def quotes():
    """
    Parametri:
      isin  (obbligatorio)  es. IT0005634800
      from  (opzionale)     data inizio yyyy-MM-dd
      to    (opzionale)     data fine   yyyy-MM-dd
    
    Risposta JSON compatibile con Portfolio Performance (JSON Quote Feed):
      [ { "date": "2025-03-01", "close": 101.03 }, ... ]
    
    Configurazione in PP:
      Provider:      JSON Quote Feed
      Feed URL:      https://<tuo-dominio>/quotes?isin=IT0005634800
      Path to Date:  $[*].date
      Path to Close: $[*].close
    """
    isin = request.args.get("isin", "").strip().upper()
    if not isin:
        return jsonify({"error": "Parametro 'isin' obbligatorio"}), 400
    if not validate_isin(isin):
        return jsonify({"error": f"ISIN non valido: {isin}"}), 400

    from_date = request.args.get("from")
    to_date = request.args.get("to")

    try:
        data = get_quotes_cached(isin)
    except RuntimeError as e:
        log.error("Scraping error for %s: %s", isin, e)
        return jsonify({"error": str(e)}), 502

    if not data:
        return jsonify({"error": f"Nessuna quotazione trovata per {isin}"}), 404

    # Filtra per date se richiesto
    if from_date:
        data = [q for q in data if q["date"] >= from_date]
    if to_date:
        data = [q for q in data if q["date"] <= to_date]

    return jsonify(data)


@app.route("/")
def index():
    """Pagina di documentazione."""
    html = """
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <title>BTP Quotes Service</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
    h1 { color: #1a5276; }
    h2 { color: #2874a6; border-bottom: 1px solid #aed6f1; padding-bottom: 6px; }
    code { background: #f4f6f7; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
    pre { background: #f4f6f7; padding: 16px; border-radius: 8px; overflow-x: auto; }
    .badge { display: inline-block; background: #1a5276; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-right: 6px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #d5d8dc; padding: 8px 12px; text-align: left; }
    th { background: #eaf2ff; }
  </style>
</head>
<body>
  <h1>📈 BTP Quotes Service</h1>
  <p>Webservice per le quotazioni storiche dei BTP italiani da Borsa Italiana,
     in formato compatibile con <strong>Portfolio Performance</strong>.</p>

  <h2>Endpoint disponibili</h2>

  <h3><span class="badge">GET</span> <code>/quotes</code></h3>
  <table>
    <tr><th>Parametro</th><th>Richiesto</th><th>Descrizione</th><th>Esempio</th></tr>
    <tr><td>isin</td><td>✅</td><td>Codice ISIN del BTP</td><td>IT0005634800</td></tr>
    <tr><td>from</td><td>❌</td><td>Data inizio (yyyy-MM-dd)</td><td>2025-01-01</td></tr>
    <tr><td>to</td><td>❌</td><td>Data fine (yyyy-MM-dd)</td><td>2025-12-31</td></tr>
  </table>

  <p><strong>Esempio:</strong><br>
  <code>/quotes?isin=IT0005634800&from=2025-01-01</code></p>

  <pre>[
  { "date": "2025-02-25", "close": 100.50 },
  { "date": "2025-02-26", "close": 100.73 },
  ...
]</pre>

  <h3><span class="badge">GET</span> <code>/health</code></h3>
  <p>Verifica che il servizio sia attivo.</p>

  <h2>Configurazione in Portfolio Performance</h2>
  <ol>
    <li>Apri il titolo BTP → tab <strong>Quotazioni storiche</strong></li>
    <li>Scegli provider: <strong>JSON Quote Feed</strong></li>
    <li>Feed URL: <code>https://&lt;tuo-dominio&gt;/quotes?isin=IT0005634800</code></li>
    <li>Path to Date: <code>$[*].date</code></li>
    <li>Path to Close: <code>$[*].close</code></li>
  </ol>

  <h2>Fonte dati</h2>
  <p>I prezzi sono il <strong>prezzo ufficiale giornaliero</strong> del listino MOT di Borsa Italiana.
     La cache viene aggiornata ogni ora.</p>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
