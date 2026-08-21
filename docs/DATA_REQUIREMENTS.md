# Data Requirements & Validation Specification

This document defines the schema, normalization processes, and data quality check rules for stock candle data ingested into the system.

---

## 1. Schema Definition

All market data is normalized to the following standard Candle schema:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | UTC Datetime | The opening timestamp of the candle |
| `symbol` | String | Exchange ticker symbol (e.g., `RELIANCE`) |
| `exchange` | String | NSE, BSE, etc. |
| `timeframe` | String | Standard timeframe identifier (`5m`, `15m`, `30m`, `1h`, `4h`, `daily`, `weekly`) |
| `open` | Decimal | Opening price |
| `high` | Decimal | Highest price during the interval |
| `low` | Decimal | Lowest price during the interval |
| `close` | Decimal | Closing price |
| `volume` | Float | Volume of shares traded during the interval |

---

## 2. Timeframe Derivation Rules

The backend requires correct timeframe relationships:
1. **Derivation Allowed**: Deriving higher timeframes from lower timeframes (e.g., combining four `1h` candles to produce a `4h` candle, or 5 trading days to produce a `weekly` candle).
2. **Derivation Prohibited**: Never derive a lower timeframe from a higher timeframe (e.g., deriving `15m` from `1h` or `daily` from `weekly`).
3. **Alignment**: Aggregated candle timestamps must align with standard intervals (e.g., a `daily` candle timestamp must begin at `00:00:00` or local market open, and aggregate all candles of the day).

---

## 3. Data Validation & Quality Checks

Every ingested dataset is subjected to the following automated validation rules:

1. **Duplicate Candles**: No two candles for the same symbol/timeframe may share the exact same timestamp.
2. **Missing Candles**: Report gaps in expected trading session sequences (excluding market closures/holidays).
3. **Invalid Timestamps**: Reject future timestamps or non-aligned intervals.
4. **Invalid OHLC Relationships**: Enforce physical constraints:
   $$\text{High} \ge \text{Open}$$
   $$\text{High} \ge \text{Close}$$
   $$\text{Low} \le \text{Open}$$
   $$\text{Low} \le \text{Close}$$
   $$\text{High} \ge \text{Low}$$
5. **Zero or Negative Values**: All OHLC values must be strictly positive ($> 0$). Volume must be non-negative ($\ge 0$).
6. **Abnormal Volume**: Flag volumes exceeding the rolling 20-candle standard deviation threshold by 5x (statistical warning, not hard error).
7. **Timezone Consistency**: Standardize timestamps to UTC (or consistent offset for IST Indian standard market hours).

### Data Quality Report
The validation service generates a report summary:
```json
{
  "total_candles": 1250,
  "duplicates_found": 0,
  "gaps_found": 2,
  "failed_ohlc_count": 0,
  "negative_prices_count": 0,
  "warnings": [
    "Gap detected between 2026-08-21T09:30:00 and 2026-08-21T10:00:00"
  ],
  "is_valid": true
}
```
If `is_valid` is `false`, the ingestion or analysis run must fail close.
