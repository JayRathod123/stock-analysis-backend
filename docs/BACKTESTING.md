# Backtesting Engine Specification

This document details the mechanics and metrics of the event-driven historical backtesting engine.

---

## 1. Execution Loop & Look-Ahead Bias Prevention

To ensure mathematical validity, the engine processes historical data chronologically using a strict state machine:

1. **Window Segmentation**: The engine advances one candle at a time ($t = 0, 1, 2, \dots$).
2. **Strict Time Cutoff**: At step $t$, the analysis subsystem is only allowed to see candles $\{C_0, C_1, \dots, C_t\}$. Indicators, market structure, and zone boundaries are recalculated solely using this historical subset. Any information from $C_{t+1}$ or later is hidden.
3. **Zone Update & Execution**: 
   - Existing active zones are updated by checking if candle $C_t$ penetrates their boundaries.
   - Fresh zones detected at $C_t$ are evaluated.
   - If a valid setup exists, a simulated trade is marked as **PENDING**.
   - If candle $C_t$ triggers the entry price of a pending setup, the trade goes **ACTIVE**.
   - The engine monitors the trade in subsequent steps $t+x$ for target hits or stop-loss trigger events.

---

## 2. Simulation Metrics

For each backtest run, the engine computes:

### Summary Performance Metrics
- **Total Trades**: Total executed trades.
- **Wins / Losses**: Trades hitting targets vs. stop losses.
- **Win Rate**: $\text{Wins} / \text{Total Trades}$.
- **Expectancy (R)**: Average R-multiple gained or lost per trade:
  $$\text{Expectancy} = \frac{\sum (\text{Profit or Loss}) / \text{Initial Risk}}{\text{Total Trades}}$$
- **Profit Factor**: Sum of gross profits divided by gross losses.
- **Max Drawdown**: Maximum peak-to-trough drop in simulated equity.
- **Streak Statistics**: Maximum consecutive wins and consecutive losses.
- **Average Holding Time**: Average duration (candle count or time duration) of active trades.
- **Target Hit Rates**: Percentage of trades hitting Target 1 (T1) and Target 2 (T2).
- **SL Hit Rate**: Percentage of trades stopped out (SL).
- **MFE / MAE**: 
  - **Maximum Favorable Excursion (MFE)**: Maximum profit reached during the trade before exiting.
  - **Maximum Adverse Excursion (MAE)**: Maximum paper loss reached during the trade before exiting.

---

## 3. Dimensional Performance breakdowns

The engine groups outcomes to analyze performance across variables:
- **By Zone Score**: Grouped by rating (A+, Strong, Watch).
- **By Freshness**: Outcomes of fresh entries vs. first or second retests.
- **By Timeframe**: Performance comparison across `5m`, `15m`, `30m`, `1h`, `4h`, `daily`, `weekly`.
- **By Pattern**: Performance of continuation patterns (RBR, DBD) vs. reversal patterns (DBR, RBD).
- **By Trend Alignment**: Trades taken inline with higher timeframe trends vs. counter-trend trades.
- **By Participation Proxy & Authentication Scores**: Correlation of trade outcomes with high/low score bands.
- **By Risk/Reward (R:R)**: Comparison of setups with different risk parameters.
