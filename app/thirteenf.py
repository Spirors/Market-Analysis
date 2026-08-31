"""Superinvestor 13F holdings from SEC EDGAR (free, no key).

Holdings are reported as WEIGHT % of each fund's disclosed portfolio value.
Dollar values are never displayed: the EDGAR `value` column switched units
($ thousands -> dollars) across filing years, so unit-guessing would violate
the no-fabrication rule. Failed funds surface as errors/omissions, never
placeholder numbers.

SEC fair-use policy requires a declared User-Agent on every request; requests
are sequential and well under published rate limits. Since 2026 www.sec.gov
(ticker map + filing archives) sits behind a bot wall that 403s plain-Python
TLS handshakes regardless of User-Agent, so fetches go through curl_cffi with
browser-TLS impersonation while keeping the declared SEC User-Agent header.
data.sec.gov (submissions API) still accepts plain clients.

Defines :class:`HoldingsAdapter` — a structural Protocol describing the
public surface consumed by callers (``service.py``, ``analysis.py``).  The
yfinance-equivalent adapter here is EDGAR-backed; future paid sources can
plug in by implementing the same shape.

# Changelog:
# 2026-08-30 — thirteenf: Added HoldingsAdapter Protocol.  Behavior: none
#              (pure refactor).
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from curl_cffi import requests as _creq

from . import config, store


@runtime_checkable
class HoldingsAdapter(Protocol):
    """Structural Protocol for holdings-data providers.

    The EDGAR implementation in this module satisfies it.  Shapes diverge
    from :class:`~app.market.MarketDataAdapter` (holdings, not quotes), so
    a separate protocol is appropriate.
    """

    def build_thirteenf(self) -> dict[str, Any]: ...

USER_AGENT = "MarketAnalysisTool/1.0 (local research app)"
REQUEST_TIMEOUT = 20  # seconds per request; keeps worst-case refresh bounded
REQUEST_GAP = 0.35    # seconds between requests; stays well under SEC limits

_TOP_N = 10

_last_request_at = 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(url: str) -> bytes:
    """GET with a declared User-Agent; paced sequentially.

    Uses curl_cffi browser-TLS impersonation: www.sec.gov 403s plain-Python
    TLS handshakes regardless of headers (bot wall), while the declared SEC
    User-Agent is still sent to honor fair-use policy. Response content is
    already decompressed by curl_cffi.
    """
    global _last_request_at
    wait = REQUEST_GAP - (time.time() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    try:
        r = _creq.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            impersonate="chrome",
        )
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
        data = r.content
    finally:
        _last_request_at = time.time()
    return data


def _get_json(url: str) -> Any:
    return json.loads(_get(url).decode("utf-8"))


# ---- Issuer -> ticker mapping (one-time fetch, cached on disk) ----

_PUNCT_RE = re.compile(r"[^A-Z0-9]+")


def _norm_issuer(name: str) -> str:
    """Normalize an issuer name for conservative exact matching."""
    return " ".join(_PUNCT_RE.sub(" ", (name or "").upper()).split())


def issuer_ticker_map() -> dict[str, str]:
    """Normalized issuer title -> ticker from SEC's company_tickers.json.

    That file carries no CUSIPs ({cik_str, ticker, title} only), so holdings
    are matched by normalized issuer NAME; unmatched issuers stay ticker=null.
    """
    path = config.CACHE_DIR / "company_tickers.json"
    cached = store.load_json(path)
    if isinstance(cached, dict) and cached:
        return cached
    try:
        raw = _get_json("https://www.sec.gov/files/company_tickers.json")
    except Exception:
        return dict(cached) if isinstance(cached, dict) else {}
    out: dict[str, str] = {}
    for row in raw.values():
        key = _norm_issuer(row.get("title") or "")
        ticker = row.get("ticker")
        if key and ticker and key not in out:
            out[key] = ticker
    if out:
        store.save_json(path, out)
    return out


# ---- Per-fund fetch + parse ----

def _latest_13f_accession(cik: int) -> tuple[str, str]:
    """(accessionNumber, reportDate) of the most recent 13F-HR for a CIK.

    A later-filed 13F-HR/A supersedes a same-period original.
    Raises ValueError when the filer has no 13F-HR filings at all.
    """
    data = _get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    periods = recent.get("reportDate") or []
    filed = recent.get("filingDate") or []
    accs = recent.get("accessionNumber") or []
    best_key: tuple[str, str] | None = None
    best_acc: str | None = None
    best_period: str | None = None
    for form, period, fdate, acc in zip(forms, periods, filed, accs):
        if form not in ("13F-HR", "13F-HR/A") or not (period and acc):
            continue
        key = (period, fdate or "")
        if best_key is None or key > best_key:
            best_key, best_acc, best_period = key, acc, period
    if not best_acc or not best_period:
        raise ValueError("no 13F-HR filings found")
    return best_acc, best_period


def _archive_url(cik: int, accession: str) -> str:
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik}/{accession.replace('-', '')}"
    )


def _info_table_url(archive: str) -> str:
    """URL of the information-table XML inside a filing archive.

    Skips primary_doc.xml; prefers files named like an info table.
    """
    idx = _get_json(f"{archive}/index.json")
    items = ((idx.get("directory") or {}).get("item")) or []
    xml_names = [
        i.get("name", "") for i in items
        if i.get("name", "").lower().endswith(".xml")
        and "primary_doc" not in i.get("name", "").lower()
    ]
    preferred = [
        n for n in xml_names
        if "infotable" in n.lower() or "informationtable" in n.lower()
    ]
    name = (preferred or xml_names or [None])[0]
    if not name:
        raise ValueError("no information-table XML in filing archive")
    return f"{archive}/{name}"


def _local(tag: str) -> str:
    """Local part of an XML tag (namespaces vary between filers)."""
    return tag.rsplit("}", 1)[-1]


def _parse_info_table(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Rows of {issuer, value} matched by element LOCAL name."""
    root = ET.fromstring(xml_bytes)
    rows: list[dict[str, Any]] = []
    for node in root.iter():
        if _local(node.tag) != "infoTable":
            continue
        issuer = None
        value: float | None = None
        for child in node.iter():
            tag = _local(child.tag)
            text = (child.text or "").strip()
            if not text:
                continue
            if tag == "nameOfIssuer" and issuer is None:
                issuer = text
            elif tag == "value" and value is None:
                try:
                    value = float(text)
                except ValueError:
                    value = None
        if issuer and value is not None:
            rows.append({"issuer": issuer, "value": value})
    return rows


def _build_fund(name: str, cik: int, quarter: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate rows by issuer and express each as % of reported value."""
    agg: dict[str, float] = {}
    total = 0.0
    for r in rows:
        agg[r["issuer"]] = agg.get(r["issuer"], 0.0) + r["value"]
        total += r["value"]
    tickers = issuer_ticker_map()

    top: list[dict[str, Any]] = []
    for issuer, value in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:_TOP_N]:
        weight = round(value / total * 100, 1) if total else None
        top.append({
            "issuer": issuer,
            "ticker": tickers.get(_norm_issuer(issuer)),
            "weight_pct": weight,
        })
    return {
        "name": name,
        "cik": cik,
        "quarter": quarter,
        "n_positions": len(agg),
        "top": top,
    }


def _cache_path(cik: int, quarter: str) -> Any:
    return config.CACHE_DIR / f"13f_{cik}_{quarter}.json"


def _fund_snapshot(name: str, cik: int) -> tuple[dict[str, Any] | None, str | None]:
    """Live-fetch one fund; fall back to stale cache; else error string."""
    try:
        accession, quarter = _latest_13f_accession(cik)
        # Unchanged quarter + fresh per-fund cache: skip the archive fetches.
        cached = store.load_json(_cache_path(cik, quarter))
        if (
            isinstance(cached, dict)
            and isinstance(cached.get("fund"), dict)
            and time.time() - cached.get("cached_at", 0) < config.THIRTEENF_TTL
        ):
            return cached["fund"], None
        rows = _parse_info_table(
            _get(_info_table_url(_archive_url(cik, accession)))
        )
        if not rows:
            raise ValueError("information table parsed to zero rows")
        fund = _build_fund(name, cik, quarter, rows)
        store.save_json(
            _cache_path(cik, quarter),
            {"cached_at": time.time(), "as_of": _now_iso(), "fund": fund},
        )
        return fund, None
    except Exception as e:
        # Serve any stale cache for this fund, stamped with its own as_of.
        for p in sorted(config.CACHE_DIR.glob(f"13f_{cik}_*.json"), reverse=True):
            cached = store.load_json(p)
            if isinstance(cached, dict) and cached.get("fund"):
                return cached["fund"], None
        return None, f"{name}: {type(e).__name__}: {e}"


_SNAPSHOT_CACHE = "thirteenf_snapshot.json"


def _apply_fund_meta(payload: dict[str, Any]) -> dict[str, Any]:
    """Stamp manager/link from config onto each fund.

    Applied at assembly time so cached payloads (snapshot + per-quarter)
    pick up config edits without invalidation; no fetching involved.
    """
    by_cik = {int(e["cik"]): e for e in config.SUPERINVESTORS}
    for fund in payload.get("funds") or []:
        entry = by_cik.get(int(fund.get("cik") or 0))
        if entry:
            fund["manager"] = entry.get("manager")
            fund["link"] = entry.get("link")
    return payload


def build_thirteenf() -> dict[str, Any]:
    """Dashboard payload: cache-first snapshot of all tracked superinvestors.

    Normal refreshes never hit EDGAR while the snapshot is within
    THIRTEENF_TTL; a stale snapshot triggers a sequential rebuild where each
    fund reuses its per-quarter cache when still fresh.
    """
    snap_path = config.CACHE_DIR / _SNAPSHOT_CACHE
    snap = store.load_json(snap_path)
    if (
        isinstance(snap, dict)
        and time.time() - snap.get("cached_at", 0) < config.THIRTEENF_TTL
        and isinstance(snap.get("payload"), dict)
    ):
        return _apply_fund_meta(snap["payload"])

    funds: list[dict[str, Any]] = []
    errors: list[str] = []
    quarters: list[str] = []
    for entry in config.SUPERINVESTORS:
        name, cik = entry["name"], int(entry["cik"])
        fund, error = _fund_snapshot(name, cik)
        if error:
            errors.append(error)
        if fund:
            funds.append(fund)
            quarters.append(fund.get("quarter") or "")
    funds.sort(key=lambda f: f["name"])

    quarter: str | None = None
    counts = Counter(q for q in quarters if q)
    if counts:
        quarter = counts.most_common(1)[0][0]

    payload = {"as_of": _now_iso(), "quarter": quarter, "funds": funds, "errors": errors}
    # Persist the rebuild only when it is usable: at least one fund
    # succeeded, or EDGAR reported no errors at all. A total failure must
    # not overwrite the last good snapshot with an empty payload that would
    # otherwise be served for THIRTEENF_TTL (~20 days).
    if funds or not errors:
        store.save_json(snap_path, {"cached_at": time.time(), "payload": payload})
    return _apply_fund_meta(payload)
