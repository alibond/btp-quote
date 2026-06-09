# BTP Quotes Service

Webservice Python che scrapa automaticamente le quotazioni BTP da Borsa Italiana
e le serve in formato JSON compatibile con Portfolio Performance.

## Installazione (una tantum)

```bash
pip install flask flask-cors playwright
playwright install chromium
```

## Avvio

```bash
python app.py
```

Il servizio parte su http://localhost:5000

## Configurazione Portfolio Performance

Per ogni BTP nel portafoglio:
1. Apri il titolo → tab **Quotazioni storiche**
2. Clicca `+` → scegli **JSON Quote Feed**
3. Compila:

| Campo | Valore |
|---|---|
| Feed URL | `http://localhost:5000/quotes?isin=IT0005634800` |
| Path to Date | `$[*].date` |
| Path to Close | `$[*].close` |

Cambia solo l'ISIN per ogni BTP.

## Come funziona

- Prima chiamata: scrapa Borsa Italiana con un browser headless (Chromium)
- Cache su disco: i dati vengono salvati in `data/IT0005634800.json`
- Refresh automatico ogni ora
- Aggiornamento forzato: `http://localhost:5000/refresh?isin=IT0005634800`
