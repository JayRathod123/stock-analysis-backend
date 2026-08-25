import sys

with open("app/analysis/zones.py", "r") as f:
    content = f.read()

content = content.replace("def is_base_candle(row: pd.Series, atr_value: float) -> bool:", "def is_base_candle(row_high, row_low, row_open, row_close, atr_value: float) -> bool:")
content = content.replace("hl_range = row[\"high\"] - row[\"low\"]", "hl_range = row_high - row_low")
content = content.replace("body_range = abs(row[\"close\"] - row[\"open\"])", "body_range = abs(row_close - row_open)")

content = content.replace("closes = df[\"close\"]", "closes = df[\"close\"].values\n    opens = df[\"open\"].values\n    highs = df[\"high\"].values\n    lows = df[\"low\"].values")
content = content.replace("opens = df[\"open\"]\n    highs = df[\"high\"]\n    lows = df[\"low\"]", "")

content = content.replace("atr_val = atr.iloc[i] if not pd.isna(atr.iloc[i]) else (highs.iloc[i] - lows.iloc[i])", "atr_val = atr.iloc[i] if not pd.isna(atr.iloc[i]) else (highs[i] - lows[i])")

content = content.replace("base_rows = [df.iloc[i + k] for k in range(base_len)]", "base_rows = [(highs[i+k], lows[i+k], opens[i+k], closes[i+k]) for k in range(base_len)]")
content = content.replace("if not is_base_candle(br, atr_val):", "if not is_base_candle(br[0], br[1], br[2], br[3], atr_val):")

content = content.replace("legin = df.iloc[legin_idx]", "legin = (highs[legin_idx], lows[legin_idx], opens[legin_idx], closes[legin_idx])")
content = content.replace("legout = df.iloc[legout_idx]", "legout = (highs[legout_idx], lows[legout_idx], opens[legout_idx], closes[legout_idx])")

content = content.replace("if is_base_candle(legin, atr_val) or is_base_candle(legout, atr_val):", "if is_base_candle(legin[0], legin[1], legin[2], legin[3], atr_val) or is_base_candle(legout[0], legout[1], legout[2], legout[3], atr_val):")

content = content.replace("legin_range = legin[\"high\"] - legin[\"low\"]", "legin_range = legin[0] - legin[1]")
content = content.replace("legout_range = legout[\"high\"] - legout[\"low\"]", "legout_range = legout[0] - legout[1]")

content = content.replace("legin_dir = \"GREEN\" if legin[\"close\"] > legin[\"open\"] else \"RED\"", "legin_dir = \"GREEN\" if legin[3] > legin[2] else \"RED\"")
content = content.replace("legout_dir = \"GREEN\" if legout[\"close\"] > legout[\"open\"] else \"RED\"", "legout_dir = \"GREEN\" if legout[3] > legout[2] else \"RED\"")

content = content.replace("legout[\"close\"] <= legin[\"close\"]", "legout[3] <= legin[3]")
content = content.replace("legout[\"close\"] >= legin[\"close\"]", "legout[3] >= legin[3]")

content = content.replace("max(r[\"open\"], r[\"close\"]) for r in base_rows", "max(r[2], r[3]) for r in base_rows")
content = content.replace("min(r[\"open\"], r[\"close\"]) for r in base_rows", "min(r[2], r[3]) for r in base_rows")
content = content.replace("r[\"high\"] for r in base_rows", "r[0] for r in base_rows")
content = content.replace("r[\"low\"] for r in base_rows", "r[1] for r in base_rows")

content = content.replace("legin[\"low\"]", "legin[1]")
content = content.replace("legout[\"low\"]", "legout[1]")
content = content.replace("legin[\"high\"]", "legin[0]")
content = content.replace("legout[\"high\"]", "legout[0]")

with open("app/analysis/zones.py", "w") as f:
    f.write(content)
