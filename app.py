"""
BTP Quotes Service — solo requests + BeautifulSoup, niente Playwright.

Endpoint:
  GET /quotes?isin=IT0005634800   -> JSON per Portfolio Performance
  GET /status                     -> ISIN in cache con ultimo prezzo
  GET /                           -> documentazione
"""

import os, json, re, logging, time
from datetime import date
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests as req
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

CACHE_TTL = 3600  # 1 ora

_cache: dict = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def load_quotes(isin):
    f = DATA_DIR / f"{isin}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

def save_quotes(isin, quotes):
    seen = {q["date"]: q["close"] for q in quotes}
    result = [{"date": d, "close": c} for d, c in sorted(seen.items())]
    (DATA_DIR / f"{isin}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape_current_price(isin: str) -> float:
    url = f"https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/scheda/{isin}-MOTX.html?lang=it"
    log.info("Scraping %s", url)

    r = req.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    el = soup.select_one("span.-formatPrice strong")
    if not el:
        raise RuntimeError(f"Prezzo non trovato nella pagina per {isin}")

    text = el.get_text(strip=True).replace(",", ".")
    price = float(text)
    log.info("Prezzo %s: %s", isin, price)
    return price

# ---------------------------------------------------------------------------
# Cache + aggiornamento
# ---------------------------------------------------------------------------

def get_quotes(isin: str) -> list[dict]:
    now = time.time()
    cached = _cache.get(isin)
    if cached and (now - cached["ts"]) < CACHE_TTL:
        log.info("Cache hit per %s", isin)
        return cached["quotes"]

    price = scrape_current_price(isin)
    today = date.today().isoformat()
    existing = load_quotes(isin)
    existing.append({"date": today, "close": price})
    saved = save_quotes(isin, existing)
    _cache[isin] = {"ts": now, "quotes": saved}
    return saved

# ---------------------------------------------------------------------------
# Validazione
# ---------------------------------------------------------------------------

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

def validate_isin(isin):
    return bool(ISIN_RE.match(isin))

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.route("/quotes")
def quotes():
    isin = request.args.get("isin", "").strip().upper()
    if not isin:
        return jsonify({"error": "Parametro 'isin' obbligatorio"}), 400
    if not validate_isin(isin):
        return jsonify({"error": f"ISIN non valido: {isin}"}), 400
    try:
        data = get_quotes(isin)
    except Exception as e:
        log.error("Errore per %s: %s", isin, e)
        return jsonify({"error": str(e)}), 502

    from_date = request.args.get("from")
    to_date   = request.args.get("to")
    if from_date: data = [q for q in data if q["date"] >= from_date]
    if to_date:   data = [q for q in data if q["date"] <= to_date]

    if not data:
        return jsonify({"error": f"Nessuna quotazione per {isin}"}), 404
    return jsonify(data)


@app.route("/status")
def status():
    result = []
    for f in sorted(DATA_DIR.glob("*.json")):
        isin = f.stem
        quotes = load_quotes(isin)
        if quotes:
            cached = _cache.get(isin)
            result.append({
                "isin": isin,
                "count": len(quotes),
                "from": quotes[0]["date"],
                "to": quotes[-1]["date"],
                "last_price": quotes[-1]["close"],
                "cache_fresh": bool(cached and (time.time() - cached["ts"]) < CACHE_TTL),
            })
    return jsonify(result)


@app.route("/")
def index():
    return """<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><title>BTP Quotes</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#333}
  h1{color:#1a5276}h2{color:#2874a6;border-bottom:1px solid #aed6f1;padding-bottom:4px}
  code{background:#f4f6f7;padding:2px 6px;border-radius:4px}
  pre{background:#f4f6f7;padding:14px;border-radius:8px}
  table{border-collapse:collapse;width:100%}th,td{border:1px solid #d5d8dc;padding:8px 12px}th{background:#eaf2ff}
</style></head><body>
<h1>📈 BTP Quotes Service</h1>
<p>Acquisizione automatica del prezzo corrente BTP da Borsa Italiana.<br>
Il prezzo viene aggiornato ogni ora e accumulato giorno per giorno nel file <code>data/ISIN.json</code>.</p>

<h2>Configurazione Portfolio Performance</h2>
<table>
  <tr><th>Campo</th><th>Valore</th></tr>
  <tr><td>Provider</td><td>JSON Quote Feed</td></tr>
  <tr><td>Feed URL</td><td><code>http://localhost:5000/quotes?isin=IT0005634800</code></td></tr>
  <tr><td>Path to Date</td><td><code>$[*].date</code></td></tr>
  <tr><td>Path to Close</td><td><code>$[*].close</code></td></tr>
</table>
<p>Cambia solo l'ISIN per ogni BTP.</p>

<h2>Endpoint</h2>
<p><code>GET /quotes?isin=XXXX</code> — storico quotazioni JSON<br>
<code>GET /quotes?isin=XXXX&from=2025-01-01&to=2025-12-31</code> — con filtro date<br>
<code>GET /status</code> — ISIN caricati con statistiche e stato cache</p>

<h2>Avvio</h2>
<pre>pip install flask flask-cors requests beautifulsoup4 lxml
python app.py</pre>
</body></html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n✅  BTP Quotes Service su http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
