# 📈 Stock Data Intelligence Dashboard

> **JarNox Software Internship Assignment — v2.0**  
> A production-quality financial data platform for 10 NSE-listed stocks with real-time analytics, technical indicators, and an interactive multi-tab dashboard.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Pre-fetch stock data (recommended on first run)
```bash
cd backend
python data_loader.py
```
Downloads ~2 years of daily OHLCV data for all 10 NSE stocks via `yfinance` and caches them locally as CSV files.

### 3. Run the server
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 4. Open the dashboard
- **Dashboard →** http://localhost:8000  
- **Swagger API docs →** http://localhost:8000/docs

---

## 🗂️ Project Structure

```
stock_dashboard/
├── backend/
│   ├── main.py            ← FastAPI app with 8 REST endpoints
│   ├── data_loader.py     ← yfinance data fetching, CSV caching, derived metrics
│   └── requirements.txt    
├── frontend/
│   └── index.html        ← Full interactive dashboard (Chart.js, vanilla JS)
├── data/                 ← Auto-created CSV cache (gitignored)
└── README.md
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/companies` | GET | List all 10 supported companies with sector info |
| `/data/{symbol}?days=30&indicators=true` | GET | OHLCV + MA7/20/30/50 + RSI + MACD + Bollinger Bands |
| `/summary/{symbol}` | GET | 52W High/Low, Avg Close, Volatility, Momentum, RSI, 52W position |
| `/compare?symbol1=INFY&symbol2=TCS&days=30` | GET | Normalized comparison + correlation + volatility |
| `/market/movers` | GET | Top 5 Gainers & Losers with volume |
| `/signals/{symbol}?days=90` | GET | RSI + MACD buy/sell signal detection |
| `/volume/{symbol}?days=30` | GET | Volume trends, 20-day MA, high-volume day detection |
| `/market/overview` | GET | Market-wide snapshot: 30d returns, RSI, volatility heatmap data |

Full interactive docs at `/docs` (Swagger UI).

---

## 📊 Custom Metrics

| Metric | Formula | Interpretation |
|---|---|---|
| **Volatility Score** | `std(daily_returns) × 100` | Higher = more volatile |
| **Momentum Score** | `(avg30d − avg90d) / avg90d × 100` | Positive = bullish trend |
| **RSI (14)** | Wilder's smoothed RS | >70 overbought, <30 oversold |
| **MACD** | EMA(12) − EMA(26) | Signal crossover = trend shift |
| **Bollinger Bands** | SMA(20) ± 2×std | Price volatility envelope |
| **52W Position** | `(price − 52w_low) / range × 100` | Where price sits in yearly range |
| **Correlation** | Pearson(close1, close2) | How similarly two stocks move |

---

## 🎨 Dashboard Features

### Multi-Tab Chart Interface
- **Price & MAs** — Close price with MA7, MA20, MA50, Bollinger Bands (toggle each on/off)
- **Volume** — Daily volume bars with 20-day average, high-volume day highlighting
- **RSI / MACD** — Stacked RSI chart with overbought/oversold lines + MACD histogram
- **Signals** — Table of notable RSI+MACD crossover signals (Buy/Sell/Oversold/Overbought)
- **Heatmap** — Color-coded 30-day returns grid for all 10 companies

### Other Features
- **Market Movers banner** — Top 5 gainers and losers at a glance
- **8 KPI cards** — Price, 52W High/Low with progress bars, Volatility, Momentum, RSI pill, 52W position
- **Stock Comparison** — Normalized base-100 performance chart with correlation and volatility
- **Export to CSV** — Download currently displayed chart data
- **Dark/Light mode toggle** — Persistent theme switch
- **Time filters** — 30D / 90D / 6M / 1Y with instant chart refresh

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Backend | FastAPI + Uvicorn |
| Data | yfinance, Pandas, NumPy |
| Frontend | Vanilla HTML/CSS/JS + Chart.js 4 + chartjs-plugin-annotation |
| Cache | Local CSV files (auto-refreshed every 6 hours) |

---

## 🧪 Running Tests (Optional)

```bash
pip install pytest httpx
pytest tests/
```

---

## 🐳 Docker Deployment (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t stock-dashboard .
docker run -p 8000:8000 stock-dashboard
```

---

## ☁️ Cloud Deployment

### Render.com (Free Tier)
1. Push to GitHub
2. Create a new **Web Service** on Render
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`

### Railway / Fly.io
Same pattern — point start command to `backend/main.py` with uvicorn.

---

## 💡 Design Decisions

- **yfinance** — Zero-cost, no-API-key access to NSE historical data
- **CSV cache** — Avoids rate-limiting; refreshes every 6 hours automatically
- **Dependency-free frontend** — No build step; works out of the box with a single HTML file
- **Indicators computed server-side** — Consistent results, less JS computation
- **FastAPI** — Auto-generates OpenAPI/Swagger docs; async-ready for future scaling

---

## 📧 Submitted by

*Arabinda Mahata*  
*mahataarabinda10@gmail.com*  
Submission to: support@jarnox.com
