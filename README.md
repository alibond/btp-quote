# BTP Quotes Service — Vercel

Webservice serverless per quotazioni BTP da Borsa Italiana, compatibile con Portfolio Performance.

## Deploy su Vercel (gratuito, senza carta)

### 1. Carica su GitHub
Crea un repository pubblico su github.com e carica questi file:
```
btp-quotes-vercel/
├── api/
│   └── index.py
├── requirements.txt
├── vercel.json
└── README.md
```

### 2. Collega a Vercel
1. Vai su [vercel.com](https://vercel.com) → Sign up con il tuo account GitHub
2. Clicca **Add New Project** → importa il repository
3. Lascia tutte le impostazioni di default → clicca **Deploy**
4. In 1-2 minuti ricevi un URL tipo `https://btp-quotes.vercel.app`

### 3. Configura Portfolio Performance
Per ogni BTP:
1. Apri il titolo → tab **Quotazioni storiche**
2. Clicca `+` → **JSON Quote Feed**
3. Compila:

| Campo | Valore |
|---|---|
| Feed URL | `https://btp-quotes.vercel.app/api/quotes?isin=IT0005634800` |
| Path to Date | `$[*].date` |
| Path to Close | `$[*].close` |

Cambia solo l'ISIN per ogni BTP.

## Note importanti

- **Stateless**: Vercel non salva dati su disco. Il servizio restituisce
  solo la quotazione del giorno corrente. Lo storico viene accumulato
  automaticamente da Portfolio Performance nel suo database locale.
- **Cold start**: la prima chiamata del giorno può impiegare 2-3 secondi
  per avviare la funzione serverless.
- **Limiti free**: Vercel free permette 100GB di banda e 100.000
  invocazioni/mese — abbondantemente sufficienti per uso personale.

## Endpoint

| Endpoint | Descrizione |
|---|---|
| `GET /` | Info servizio e configurazione PP |
| `GET /api/quotes?isin=IT0005634800` | Quotazione corrente in formato PP |
