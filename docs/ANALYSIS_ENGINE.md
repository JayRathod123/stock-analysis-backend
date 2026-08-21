# Analysis Engine Specification

This document details the deterministic rules, mathematical calculations, and algorithms for detecting market structure and Supply & Demand zones.

---

## 1. Market Structure Detection

Market structure is calculated deterministically to evaluate market bias.

### Swing Highs and Swing Lows
A swing point is identified by looking at a window of candles around the target candle:
- **Swing High**: A candle at index $i$ whose high is strictly greater than the highs of $N$ candles before and $N$ candles after.
- **Swing Low**: A candle at index $i$ whose low is strictly lower than the lows of $N$ candles before and $N$ candles after.
- Parameter $N$ is configurable (default is 2, creating a 5-candle pattern).

### Break of Structure (BOS)
- **Bullish BOS**: Occurs when the close of a candle crosses above the most recent Swing High in an uptrend, confirming trend continuation.
- **Bearish BOS**: Occurs when the close of a candle crosses below the most recent Swing Low in a downtrend, confirming trend continuation.

### Change of Character (CHoCH)
- **Bullish CHoCH**: Occurs when the close of a candle crosses above the recent Swing High that led to the lowest low, signaling a trend reversal from bearish to bullish.
- **Bearish CHoCH**: Occurs when the close of a candle crosses below the recent Swing Low that led to the highest high, signaling a trend reversal from bullish to bearish.

---

## 2. Supply and Demand Zone Detection

Zones are composed of three parts: **Leg-In**, **Base**, and **Leg-Out**.

### Zone Types
- **Demand Zones**:
  - **Drop-Base-Rally (DBR)**: Bearish Leg-In, consolidation Base, Bullish Leg-Out (Reversal).
  - **Rally-Base-Rally (RBR)**: Bullish Leg-In, consolidation Base, Bullish Leg-Out (Continuation).
- **Supply Zones**:
  - **Rally-Base-Drop (RBD)**: Bullish Leg-In, consolidation Base, Bearish Leg-Out (Reversal).
  - **Drop-Base-Drop (DBD)**: Bearish Leg-In, consolidation Base, Bearish Leg-Out (Continuation).

### Base Candle Classification
A candle is classified as a **Base Candle** if its body size is smaller than a configurable ratio of its total range:
$$\text{Body Ratio} = \frac{|\text{Close} - \text{Open}|}{\text{High} - \text{Low}} \le \text{Base Body Threshold (default 0.5)}$$

And its total range is relatively small compared to recent volatility:
$$\text{Range} < 1.5 \times \text{ATR}$$

### Thresholds
- **Base Candle Count**: 
  - 1–3 candles: Strongest zones (Preferred).
  - 4–5 candles: Weaker.
  - 6+ candles: Discarded (Garbage Filter).
- **Leg-Out Strength**: Must show strong displacement (calculated via body percentage and range/ATR ratio).
