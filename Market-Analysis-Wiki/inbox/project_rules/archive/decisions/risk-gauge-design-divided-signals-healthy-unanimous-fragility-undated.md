# Risk gauge design: divided signals = healthy, unanimous = fragility (undated)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Risk gauge design: divided signals = healthy, unanimous = fragility

In the archived `ai_market_sentiment_gauge.html`, a card's `col` is fixed
for layout; the signed `weight` is what moves the needle. `app/risk.py`
encodes the same intuition in code rather than layout: divided signals
across the 9 cross-asset inputs are healthy, unanimous optimism is the
fragility signal (RED fires on consensus optimism, not just bad numbers).
The gauge's ~70 events are also part of the news timeline seed
(`app/seed_data.py`), with direction mapped from its bear/neutral/bull
columns. Keep this framing in mind before "fixing" `app/risk.py` to fire on
raw bearishness — unanimous bearishness is not the RED trigger, unanimous
*optimism* is.

