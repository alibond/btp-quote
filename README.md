# QuoteFeed

QuoteFeed — webservice serverless per quotazioni finanziarie, compatibile con **Portfolio Performance**.

Fonti supportate:
- **BTP italiani** → scraping Borsa Italiana
- **Fondi comuni e previdenziali** → scraping Teleborsa

---

## Deploy su Vercel (gratuito, senza carta)

### 1. Carica su GitHub
Crea un repository su github.com e carica questi file:
```
├── api/
│   └── index.py
├── requirements.txt
├── vercel.json
└── README.md
```

### 2. Collega a Vercel
1. Vai su [vercel.com](https://vercel.com) → Sign up con account GitHub
2. **Add New Project** → importa il repository
3. Lascia le impostazioni di default → **Deploy**
4. In 1-2 minuti ricevi un URL tipo `https://quotefeed.vercel.app`

---

## Endpoint disponibili

### `GET /api/quotes` — BTP italiani

Recupera il prezzo corrente di un BTP da Borsa Italiana.

**Parametro:** `isin` (codice ISIN del titolo)

**Esempio:**
```
https://quotefeed.vercel.app/api/quotes?isin=IT0005634800
```

**Risposta:**
```json
[{ "date": "2026-06-10", "close": 98.90 }]
```

**Configurazione Portfolio Performance:**

| Campo | Valore |
|---|---|
| Provider | JSON Quote Feed |
| Feed URL | `https://quotefeed.vercel.app/api/quotes?isin=IT0005634800` |
| Path to Date | `$[*].date` |
| Path to Close | `$[*].close` |

Per ogni BTP cambia solo l'ISIN nell'URL.

---

### `GET /api/fondo` — Fondi comuni e previdenziali

Recupera il prezzo corrente (NAV) di un fondo da Teleborsa.

**Parametro:** `slug` (parte finale dell'URL Teleborsa del fondo)

Per trovare lo slug di un fondo:
1. Cerca il fondo su [teleborsa.it](https://www.teleborsa.it)
2. Copia la parte finale dell'URL, ad esempio:
   ```
   https://www.teleborsa.it/fondi/allianz-previdenza-l-azionaria-alpfra05-RkMuQUxQRlJBMDU
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                   questo è lo slug
   ```

**Esempi:**

Linea Azionaria:
```
https://quotefeed.vercel.app/api/fondo?slug=allianz-previdenza-l-azionaria-alpfra05-RkMuQUxQRlJBMDU
```

Linea Flessibile Garanzia Rest. Capitale:
```
https://quotefeed.vercel.app/api/fondo?slug=allianz-previdenza-l-flessibile-garanzia-rest-capitale-alpfrg01-RkMuQUxQRlJHMDE
```

**Risposta:**
```json
[{ "date": "2026-06-03", "close": 34.648 }]
```

> ⚠️ Il separatore decimale viene convertito automaticamente da virgola (`,`) a punto (`.`)
> come richiesto da Portfolio Performance.

**Configurazione Portfolio Performance:**

| Campo | Valore |
|---|---|
| Provider | JSON Quote Feed |
| Feed URL | `https://quotefeed.vercel.app/api/fondo?slug=<slug>` |
| Path to Date | `$[*].date` |
| Path to Close | `$[*].close` |

Questo endpoint funziona con qualsiasi fondo presente su Teleborsa, non solo quelli Allianz.

---

## Note

- **Stateless**: Vercel non salva dati tra una chiamata e l'altra. Il servizio
  restituisce sempre solo la quotazione del giorno corrente. Lo storico viene
  accumulato automaticamente da Portfolio Performance nel suo database locale
  giorno dopo giorno.
- **Cold start**: la prima chiamata dopo un periodo di inattività può impiegare
  2-3 secondi per avviare la funzione serverless.
- **Limiti free**: Vercel free permette 100GB di banda e 100.000
  invocazioni/mese — ampiamente sufficienti per uso personale.
- **Aggiornamento codice**: ogni push su GitHub aggiorna automaticamente
  il servizio su Vercel senza necessità di rideploy manuale.
