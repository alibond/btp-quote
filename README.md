# BTP Quotes Service

Webservice Python/Flask che scrapa le quotazioni storiche dei BTP da Borsa Italiana
e le espone in formato JSON compatibile con **Portfolio Performance**.

## Struttura file

```
btp-quotes/
├── app.py            # Applicazione principale
├── requirements.txt  # Dipendenze Python
├── Procfile          # Comando di avvio per Render/Heroku
├── render.yaml       # Configurazione deploy automatico Render.com
└── README.md
```

---

## Deploy gratuito su Render.com (raccomandato)

### 1. Crea un repository GitHub
1. Vai su [github.com](https://github.com) e crea un nuovo repository (es. `btp-quotes`)
2. Carica tutti i file di questa cartella nel repository

### 2. Collegati a Render.com
1. Vai su [render.com](https://render.com) e crea un account gratuito (nessuna carta richiesta)
2. Clicca **New → Web Service**
3. Collega il tuo account GitHub e seleziona il repository `btp-quotes`
4. Render rileva automaticamente `render.yaml` e configura tutto

### 3. Avvia il deploy
- Clicca **Create Web Service**
- Il deploy richiede circa 2 minuti
- Al termine ricevi un URL tipo: `https://btp-quotes.onrender.com`

> ⚠️ **Nota sul piano free di Render**: il servizio va in "sleep" dopo 15 minuti
> di inattività. La prima richiesta dopo una pausa impiega ~30 secondi per
> svegliarsi. Per uso quotidiano con PP questo non è un problema.

---

## Configurazione in Portfolio Performance

Per ogni BTP nel tuo portafoglio:

1. Apri il titolo → tab **Quotazioni storiche**
2. Clicca `+` → scegli **JSON Quote Feed**
3. Compila i campi:

| Campo | Valore |
|---|---|
| Feed URL | `https://btp-quotes.onrender.com/quotes?isin=IT0005634800` |
| Path to Date | `$[*].date` |
| Path to Close | `$[*].close` |

4. Clicca **Test** per verificare che i dati arrivino
5. Clicca **OK**

Per aggiungere un altro BTP cambia solo l'ISIN nell'URL:
```
https://btp-quotes.onrender.com/quotes?isin=IT0005584849
```

---

## Esecuzione locale (opzionale)

```bash
# Installa dipendenze
pip install -r requirements.txt

# Avvia il server
python app.py

# Testa nel browser
http://localhost:5000/quotes?isin=IT0005634800
```

---

## Formato JSON restituito

```json
[
  { "date": "2025-02-25", "close": 100.50 },
  { "date": "2025-02-26", "close": 100.73 },
  { "date": "2025-02-27", "close": 101.03 }
]
```

- `date`: formato `yyyy-MM-dd` (riconosciuto automaticamente da PP)
- `close`: prezzo ufficiale MOT (valore nominale, es. 101.03 = 101,03%)

---

## Endpoint disponibili

| Endpoint | Descrizione |
|---|---|
| `GET /` | Documentazione web |
| `GET /health` | Stato del servizio |
| `GET /quotes?isin=XXXX` | Quotazioni storiche complete |
| `GET /quotes?isin=XXXX&from=2025-01-01` | Con filtro data inizio |
| `GET /quotes?isin=XXXX&from=2025-01-01&to=2025-06-30` | Con filtro date |

---

## Note tecniche

- **Fonte dati**: Listino Ufficiale MOT di Borsa Italiana
- **Cache**: 1 ora in memoria (evita troppe richieste a Borsa Italiana)
- **Rate limiting**: nessuno (uso personale)
- **Aggiornamento prezzi**: i prezzi del giorno corrente diventano disponibili
  sul listino ufficiale la sera/notte successiva
