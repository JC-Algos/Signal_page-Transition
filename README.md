# JC Algos Signal - Trading Signal Analysis Platform

A modern web application for analyzing trading signals from Telegram, with real-time stock data integration via Yahoo Finance.

![JC Algos Signal](https://img.shields.io/badge/JC%20Algos-Signal-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-green?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-red?style=for-the-badge&logo=flask)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

## Features

- 🔐 **Email Authentication** - Secure access for authorized users
- 📊 **Signal Analysis** - Buy/Sell signal detection with validation
- 📈 **Real-time Data** - Live stock prices via Yahoo Finance
- 🌍 **Multi-Exchange Support** - HKEX, US, Shanghai, Shenzhen, Forex
- 📉 **P/L Tracking** - Automatic profit/loss calculation
- 📜 **Signal History** - Historical data storage and analysis
- 📱 **Responsive Design** - Works on desktop and mobile
- 🚀 **Docker Ready** - Easy deployment with Docker

## Screenshots

### Dashboard
The main dashboard shows signal statistics and detailed data in a clean, modern interface.

### Signal Analysis
Real-time analysis of trading signals with validation and P/L calculation.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js (optional, for development)
- Telegram API credentials

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/JC-Algos/jc-algos-signal-web.git
cd jc-algos-signal-web
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Run the application**
```bash
cd backend
python app.py
```

4. **Open in browser**
```
http://localhost:5000
```

## Docker Deployment

```bash
# Build the image
docker build -t jc-algos-signal .

# Run the container
docker run -d -p 5000:5000 --name jc-algos jc-algos-signal
```

## Project Structure

```
jc-algos-signal-web/
├── backend/
│   └── app.py              # Flask API server
├── frontend/
│   ├── index.html          # Main HTML page
│   ├── css/
│   │   └── style.css       # Styles
│   └── js/
│       └── app.js          # Frontend JavaScript
├── data/
│   └── signals.db          # SQLite database
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker configuration
└── README.md               # Documentation
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Authenticate user |
| `/api/exchanges` | GET | Get available exchanges |
| `/api/signals/fetch` | POST | Fetch signals from Telegram |
| `/api/signals/history/{exchange}` | GET | Get signal history |
| `/api/signals/export` | POST | Export signals as CSV |

## Configuration

### Telegram API
The application uses Telegram API to fetch signals. Update these credentials in `backend/app.py`:

```python
API_ID = "your_api_id"
API_HASH = "your_api_hash"
CHAT_ID = your_chat_id
SESSION_STRING = "your_session_string"
```

### Authorized Emails
Add authorized emails to the `APPROVED_EMAILS` list in `backend/app.py`:

```python
APPROVED_EMAILS = [
    "user1@example.com",
    "user2@example.com",
]
```

## Exchanges Supported

- **HKEX** - Hong Kong Stock Exchange
- **BATS** - US Markets (BATS Exchange)
- **SSE** - Shanghai Stock Exchange
- **SZSE** - Shenzhen Stock Exchange
- **OANDA** - Forex Markets
- **HSI** - Hang Seng Index

## Signal Validation Logic

### Standard Signals
- **Bullish (好)**: Valid if Trigger Day Close >= Trigger Price
- **Bearish (淡)**: Valid if Trigger Day Close <= Trigger Price

### Magic 9/13 Strategy (Reversed)
- **Bullish (好)**: Valid if Trigger Day Close <= Trigger Price
- **Bearish (淡)**: Valid if Trigger Day Close >= Trigger Price

## P/L Calculation

### Bullish Signals
```
P/L% = ((Present Close / Trigger Price) - 1) × 100
```

### Bearish Signals
```
P/L% = ((Trigger Price / Present Close) - 1) × 100
```

## Deployment Options

### 1. Traditional Server
```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:5000 backend.app:app
```

### 2. Docker
```bash
docker-compose up -d
```

### 3. Cloud Platforms
- **Heroku**: Use Procfile
- **Railway**: Direct deployment
- **Render**: Dockerfile support
- **AWS/GCP**: Container services

## Development

### Running in Development Mode
```bash
cd backend
export FLASK_ENV=development
python app.py
```

### Frontend Development
The frontend is built with vanilla JavaScript - no build step required. Simply edit files in `frontend/` and refresh the browser.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please visit [JC Algo Patreon](https://www.patreon.com/c/JC_Algo) or contact the development team.

---

**Built with ❤️ by JC Algos**
