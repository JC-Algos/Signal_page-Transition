# JC Algos Signal Analysis System

Trading signal analysis platform with frontend and backend API.

## Architecture

```
┌─────────────────────────┐     ┌─────────────────────────┐
│  Frontend (Hostinger)   │     │  Backend API (VPS)      │
│  - index.html           │────▶│  - FastAPI server       │
│  - signals.html         │◀────│  - Telegram integration │
│  - history.html         │     │  - Yahoo Finance data   │
└─────────────────────────┘     └─────────────────────────┘
```

## Project Structure

```
Signal_page-Transition/
├── frontend/
│   ├── index.html        # Homepage
│   ├── signals.html      # Signal analysis page
│   └── history.html      # Historical records page
├── backend/
│   ├── main.py           # FastAPI application
│   ├── requirements.txt  # Python dependencies
│   └── stats/            # Signal history CSV files (auto-created)
├── app.py                # Original Streamlit app (standalone)
├── requirements.txt      # Streamlit app dependencies
└── README.md
```

## Deployment

### Backend (VPS)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/JC-Algos/Signal_page-Transition.git
   cd Signal_page-Transition/backend
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the API server:**
   ```bash
   # Development
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload

   # Production (with process manager)
   pip install gunicorn
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
   ```

5. **Run as a service (systemd):**
   ```bash
   sudo nano /etc/systemd/system/jcalgos-api.service
   ```

   ```ini
   [Unit]
   Description=JC Algos Signal API
   After=network.target

   [Service]
   User=your_user
   WorkingDirectory=/path/to/Signal_page-Transition/backend
   ExecStart=/path/to/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl enable jcalgos-api
   sudo systemctl start jcalgos-api
   ```

### Frontend (Hostinger)

1. **Update API URL:**
   
   Edit each HTML file and change `API_BASE` to your VPS URL:
   ```javascript
   const API_BASE = 'https://your-vps-domain.com';
   ```

2. **Upload files:**
   
   Upload the contents of `frontend/` folder to your Hostinger public_html directory.

3. **CORS Configuration:**
   
   The backend is configured to accept all origins (`*`). For production, update `main.py`:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-hostinger-domain.com"],
       ...
   )
   ```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/api/signals` | GET | Fetch trading signals |
| `/api/history/{exchange}` | GET | Get signal history |
| `/api/build-history` | POST | Build history for multiple dates |
| `/api/exchanges` | GET | List available exchanges |

### Query Parameters for `/api/signals`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| exchange | string | HKEX | Exchange: HKEX, BATS, SSE_DLY, ZSE_DLY, OANDA |
| days | int | 1 | Days to look back (1-30) |
| from_date | string | - | Start date (YYYY-MM-DD) |
| to_date | string | - | End date (YYYY-MM-DD) |
| sort_by_sentiment | bool | true | Sort by sentiment (好 first) |
| sort_by_pl | bool | false | Sort by P/L |
| pl_order | string | desc | P/L sort order: asc or desc |

### Query Parameters for `/api/history/{exchange}`

| Parameter | Type | Description |
|-----------|------|-------------|
| from_date | string | Start date filter (YYYY-MM-DD) |
| to_date | string | End date filter (YYYY-MM-DD) |

## Features

- **Real-time Signal Fetching**: Fetch signals directly from Telegram
- **Multi-Exchange Support**: Hong Kong, US, Shanghai, Shenzhen, Forex
- **Signal Validation**: Automatic validation based on trigger prices
- **P/L Calculation**: Real-time profit/loss calculation using Yahoo Finance
- **History Tracking**: Day-by-day signal statistics with CSV persistence
- **Date Range Filtering**: Filter signals and history by date range
- **CSV Export**: Download data as CSV files

## Streamlit Version

The original Streamlit app is still available:

```bash
cd Signal_page-Transition
pip install -r requirements.txt
streamlit run app.py
```

## License

© 2026 JC Algos. All rights reserved.
