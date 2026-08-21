# API Contract Specification

This document defines the REST API routes and JSON schemas exposed by the Stock Analysis Backend.

---

## 1. Endpoints Overview

All endpoints return JSON responses with standard status codes.

### System & Stock Queries
- **`GET /health`**
  Returns application and database readiness status.
- **`GET /stocks/search?query={symbol}`**
  Searches supported stock symbols (Indian markets).
- **`GET /stocks/{symbol}`**
  Retrieves stock metadata and status summaries.
- **`GET /candles?symbol={symbol}&timeframe={tf}&start={dt}&end={dt}`**
  Retrieves normalized candle history.

### Analysis & Zone Engine
- **`POST /analysis`**
  Executes an ad-hoc analysis run for a given symbol and timeframes. Returns the analysis run summary.
- **`GET /analysis/{id}`**
  Retrieves a historical analysis run output.
- **`GET /zones?symbol={symbol}&status={status}`**
  Retrieves all tracked supply/demand zones.
- **`GET /zones/{id}`**
  Retrieves detailed metrics of a specific zone.

### Backtesting Subsystem
- **`POST /backtests`**
  Triggers a historical backtest run.
- **`GET /backtests/{id}`**
  Retrieves summary metrics of a backtest run.
- **`GET /backtests/{id}/trades`**
  Retrieves list of trades executed during the backtest.

### AI Explanation Layer
- **`POST /ai/explain`**
  Accepts a deterministic setup summary and feeds it into the local Ollama provider to generate a natural language narrative.

---

## 2. Core Schemas (Pydantic Models)

### Analysis Response Model (`POST /analysis`)
```json
{
  "id": "uuid-v4",
  "symbol": "RELIANCE",
  "current_price": 2450.50,
  "market_bias": "BULLISH",
  "intraday_bias": "BULLISH",
  "swing_bias": "SIDEWAYS",
  "best_intraday_setup": {
    "zone_id": "uuid-zone-1",
    "zone_type": "DEMAND",
    "pattern": "DBR",
    "timeframe": "15m",
    "freshness": "FRESH",
    "retest_count": 0,
    "authentication_score": 85,
    "participation_proxy_score": 90,
    "final_score": 88.5,
    "entry": 2435.00,
    "stop_loss": 2420.00,
    "target_1": 2470.00,
    "target_2": 2500.00,
    "risk": 15.00,
    "reward": 65.00,
    "rr": 4.33,
    "status": "ACTIVE",
    "positive_reasons": ["High relative volume", "Strong departure displacement"],
    "negative_reasons": ["Nearby resistance zone at 2510"],
    "warnings": []
  },
  "best_swing_setup": null,
  "other_valid_setups": [],
  "watchlist_zones": [],
  "rejected_zones": []
}
```

### AI Explanation Request Model (`POST /ai/explain`)
```json
{
  "setup_details": {
    "symbol": "RELIANCE",
    "zone_type": "DEMAND",
    "pattern": "DBR",
    "timeframe": "15m",
    "entry": 2435.00,
    "stop_loss": 2420.00,
    "target_1": 2470.00,
    "final_score": 88.5
  }
}
```
*Response*:
```json
{
  "explanation": "A high-quality Demand zone of type Drop-Base-Rally (DBR) has been identified on RELIANCE at the 15-minute timeframe. The zone has a score of 88.5, showing strong departure momentum. The recommended entry is at 2435.00, with a stop loss set below the distal boundary at 2420.00, targeting an exit near 2470.00. This setup provides an attractive 1:2.33 risk-to-reward ratio."
}
```
