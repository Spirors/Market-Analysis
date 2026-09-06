"""One-shot: remove stray 'test*' portfolios from data/portfolios.json.

Run once as part of the dashboard-cache-sync fix. The file is gitignored
so the cleaned result is not committed — it just prevents the 44 stray
entries from reappearing in the dashboard after the cache-patching fix
lands.
"""

import json
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "data" / "portfolios.json"
data = json.loads(path.read_text(encoding="utf-8"))
before_count = len(data.get("portfolios", {}))
data["portfolios"] = {
    k: v for k, v in data.get("portfolios", {}).items()
    if not k.startswith("test")
}
after_count = len(data.get("portfolios", {}))
path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(f"Before: {before_count} portfolios")
print(f"After:  {after_count} portfolios")
print(f"Removed: {before_count - after_count} test* entries")
print(f"Remaining: {list(data['portfolios'].keys())}")
