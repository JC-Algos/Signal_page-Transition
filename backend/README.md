# JC Algos Technical Analysis API

## Files
- `ta_api.py` - Main Flask API server
- `ta_analyzer.py` - TA analysis logic (EMA, ADX, Fibonacci, Volume Profile, etc.)
- `rrg_rs_analyzer.py` - RRG chart + RS ranking
- `generate_chart.py` - Technical chart generation with patterns

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For CJK font support (Chinese characters in charts)
apt-get install fonts-noto-cjk fonts-noto-cjk-extra
```

## Run

```bash
python ta_api.py --port 5005
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ta/health` | GET | Health check |
| `/api/ta/analyze?ticker=0700&market=HK` | GET | Full analysis with charts |
| `/api/ta/quick?ticker=0700&market=HK` | GET | Quick metrics only |
| `/api/ta/chart/<filename>` | GET | Serve chart images |
| `/api/ta/batch` | POST | Batch analysis |

## Environment Variables

- `CHART_DIR` - Directory to save charts (default: `/root/clawd/research/charts`)
