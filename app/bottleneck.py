"""Bottleneck identification (serenity-style chokepoint investing).

Encodes the framework from the installed `serenity-chokepoint-investing` skill:
trace the system architecture down to the scarce physical layer that the whole
downstream build cannot bypass, and ask whether that layer is the binding
constraint. This module maps known chokepoint layers to trackable free-data
gauges and produces a structured "bottleneck read".
"""

import math
from typing import Any

from . import config, market
from .indicators import roc_at


# Hierarchical chokepoint map. Each category is an AI demand driver split into
# upstream (scarce suppliers / enablers) and downstream (end-product builders /
# deployers). Tickers are chosen as: major players, standout mid/small caps,
# and ETFs that cover the rest of a layer.
# Categories are kept in a fixed presentation order.
BOTTLENECK_CATEGORIES = [
    {
        "category": "Agentic AI",
        "streams": {
            "upstream": [
                {
                    "layer": "Compute / ASIC / foundry",
                    "proxies": ["NVDA", "AMD", "AVGO", "TSM", "QCOM", "ARM", "CRDO", "ALAB", "SMH", "SOXX"],
                    "gauge": "Accelerator availability, foundry utilization, ASIC ramp commentary",
                    "why_scarce": "Training and inference agents require specialized silicon; leading-edge foundry capacity is concentrated",
                },
                {
                    "layer": "Advanced packaging / CoWoS",
                    "proxies": ["TSM", "AMAT", "KLAC", "LRCX"],
                    "gauge": "Foundry + equipment names pricing in capacity; watch margin/guidance",
                    "why_scarce": "CoWoS capacity is the single shared substrate for high-end AI accelerators",
                },
                {
                    "layer": "Memory (HBM / DRAM / storage)",
                    "proxies": ["MU", "WDC", "STX", "SMH", "SOXX"],
                    "gauge": "Memory pricing power; DRAM/HBM sold out vs. shortage allegations",
                    "why_scarce": "HBM capacity shifts the whole memory industry's supply",
                },
                {
                    "layer": "Optics / CPO / external light source",
                    "proxies": ["LITE", "COHR", "AAOI", "SMH"],
                    "gauge": "Transceiver lead times, EML/CW laser supply locks, CPO design-ins",
                    "why_scarce": "800G/1.6T/3.2T ramp depends on qualified laser and silicon-photonics suppliers",
                },
                {
                    "layer": "Data-center power / cooling / real estate",
                    "proxies": ["VST", "CEG", "NRG", "XLU", "PLD", "DLR", "EQIX"],
                    "gauge": "Utility capex + power-constrained data-center buildout",
                    "why_scarce": "Data-center power and floor space are the binding constraints on deployment",
                },
                {
                    "layer": "Neocloud / GPU cluster capacity",
                    "proxies": ["NBIS", "CRDO", "SMCI", "DELL", "HPE", "ANET"],
                    "gauge": "Contracted GPU clusters, server/backlog ramps, networking attach",
                    "why_scarce": "Deployed compute capacity with power, financing, and customer contracts is scarce and lumpy",
                },
            ],
            "downstream": [
                {
                    "layer": "Hyperscaler cloud platforms",
                    "proxies": ["AMZN", "MSFT", "GOOGL", "META", "ORCL"],
                    "gauge": "Capex guidance, AI revenue run-rates, capacity buildout pace",
                    "why_scarce": "They monetize agentic AI at scale and set the capex tone for the whole stack",
                },
                {
                    "layer": "Agentic AI applications",
                    "proxies": ["CRM", "NOW", "SHOP", "ADBE"],
                    "gauge": "Agent products, seat pricing, workflow automation attach",
                    "why_scarce": "The end-user interface layer that converts model capability into recurring revenue",
                },
            ],
        },
    },
    {
        "category": "Autonomous Driving",
        "streams": {
            "upstream": [
                {
                    "layer": "LiDAR / camera / ADAS sensors",
                    "proxies": ["LAZR", "MBLY", "CGNX", "AMBA"],
                    "gauge": "OEM design wins, sensor suite BOM, LiDAR cost-down curves",
                    "why_scarce": "Perception hardware must be cheap enough and reliable enough for mass deployment",
                },
                {
                    "layer": "AV compute silicon",
                    "proxies": ["NVDA", "QCOM", "TSLA", "MCHP"],
                    "gauge": "Drive-computer ramps, OEM wins, power/performance benchmarks",
                    "why_scarce": "Self-driving requires dedicated, low-power, automotive-grade compute",
                },
                {
                    "layer": "HD mapping / localization",
                    "proxies": ["GOOGL", "MBLY"],
                    "gauge": "Map coverage expansion, localization partnerships",
                    "why_scarce": "High-definition environment models are a recurring data cost for AV fleets",
                },
                {
                    "layer": "Charging / EV power infrastructure",
                    "proxies": ["CHPT", "EVGO", "BLNK", "TSLA"],
                    "gauge": "Charger utilization, network buildout, fleet charging deals",
                    "why_scarce": "Electric AV fleets need dense, reliable charging networks",
                },
            ],
            "downstream": [
                {
                    "layer": "Robotaxi / ride-hail operators",
                    "proxies": ["TSLA", "GOOGL", "UBER", "LYFT"],
                    "gauge": "Miles driven, paid robotaxi rides, geographic expansion",
                    "why_scarce": "The first scalable AV revenue model; winner-take-most dynamics",
                },
                {
                    "layer": "AV OEMs",
                    "proxies": ["TSLA", "RIVN", "LCID", "GM"],
                    "gauge": "Vehicle deliveries with self-driving capability, software take rates",
                    "why_scarce": "Consumer and fleet buyers must adopt AV hardware for the ecosystem to scale",
                },
            ],
        },
    },
    {
        "category": "AI gadgets",
        "streams": {
            "upstream": [
                {
                    "layer": "Edge AI SoC",
                    "proxies": ["QCOM", "ARM", "AAPL", "TSM", "INTC"],
                    "gauge": "NPU TOPS, device design wins, premium tier mix",
                    "why_scarce": "On-device AI requires efficient NPUs; leading-edge silicon supply is concentrated",
                },
                {
                    "layer": "AR optics / displays / light engines",
                    "proxies": ["LITE", "COHR", "AAOI", "HIMX", "KOPN"],
                    "gauge": "Waveguide yield, microLED/OLED microdisplay ramps, OEM design-ins",
                    "why_scarce": "Compact, bright, efficient near-eye displays are the physical gate for AR glasses",
                },
                {
                    "layer": "Cameras / sensors",
                    "proxies": ["CGNX", "AAPL", "AMBA"],
                    "gauge": "Camera module specs, multi-sensor fusion in phones/glasses",
                    "why_scarce": "AI gadgets need always-on sensing without killing battery or form factor",
                },
                {
                    "layer": "Memory / storage",
                    "proxies": ["MU", "WDC", "STX"],
                    "gauge": "Mobile DRAM/NAND pricing, high-density storage content",
                    "why_scarce": "On-device models increase memory and storage requirements per unit",
                },
            ],
            "downstream": [
                {
                    "layer": "Smartphone OEMs",
                    "proxies": ["AAPL", "GOOGL"],
                    "gauge": "AI feature rollout, upgrade cycles, ASP/mix shift",
                    "why_scarce": "Smartphones are the first billion-unit AI gadget market",
                },
                {
                    "layer": "AR / smart-glasses OEMs",
                    "proxies": ["META", "GOOGL", "AAPL", "SNAP", "VUZI"],
                    "gauge": "Product launches, developer traction, unit ramps",
                    "why_scarce": "AR glasses are the next personal compute form factor after phones",
                },
                {
                    "layer": "App ecosystems / distribution",
                    "proxies": ["AAPL", "GOOGL", "META"],
                    "gauge": "AI app store revenue, on-device agent distribution",
                    "why_scarce": "Whoever owns distribution captures recurring AI gadget monetization",
                },
            ],
        },
    },
    {
        "category": "Robots",
        "streams": {
            "upstream": [
                {
                    "layer": "Motors / drives / actuators",
                    "proxies": ["ROK", "ETN", "EMR"],
                    "gauge": "Industrial automation backlog, motion-control demand, robot arm content",
                    "why_scarce": "Precision motion systems are a bottleneck for robot performance and cost",
                },
                {
                    "layer": "Sensors / vision / LiDAR",
                    "proxies": ["CGNX", "SMTC", "LAZR", "MBLY", "AMBA"],
                    "gauge": "Vision system lead times, LiDAR qualification, sensor fusion adoption",
                    "why_scarce": "Embodied AI depends on reliable perception; qualified sensor suppliers are concentrated",
                },
                {
                    "layer": "Edge AI / robotics semis",
                    "proxies": ["NVDA", "QCOM", "ARM", "TSM", "SMH"],
                    "gauge": "Edge AI chip launches, robot brain module ramps",
                    "why_scarce": "Low-latency onboard compute is scarce relative to cloud training silicon",
                },
                {
                    "layer": "Test / automation equipment",
                    "proxies": ["TER", "ISRG"],
                    "gauge": "Robotics test demand, surgical system production ramps",
                    "why_scarce": "Precision automation requires specialized test and validation equipment",
                },
                {
                    "layer": "Robotics ETF basket",
                    "proxies": ["BOTZ"],
                    "gauge": "Broad robotics/automation equity momentum",
                    "why_scarce": "ETF proxy for the small-cap names not individually trackable",
                },
            ],
            "downstream": [
                {
                    "layer": "Industrial automation",
                    "proxies": ["ROK", "ETN", "EMR"],
                    "gauge": "Factory automation orders, reshoring capex, robot install rates",
                    "why_scarce": "The largest near-term robot demand pool; suppliers are also deployers",
                },
                {
                    "layer": "Surgical / service robots",
                    "proxies": ["ISRG", "SYK"],
                    "gauge": "System placements, procedure growth, service attach",
                    "why_scarce": "High-value, regulated robot deployments with long replacement cycles",
                },
                {
                    "layer": "Humanoid / general-purpose robots",
                    "proxies": ["TSLA"],
                    "gauge": "Prototype-to-production milestones, cost curves, safety/regulatory progress",
                    "why_scarce": "The most visible embodied-AI endgame, but most players are private",
                },
            ],
        },
    },
]


def all_proxy_symbols() -> list[str]:
    """Every proxy ticker across all layers, deduped in definition order.

    The snapshot builder merges this into its bulk history download so layer
    ranking reads warm snapshot data instead of falling back to sequential
    per-symbol fetches on a cold cache.
    """
    seen: dict[str, None] = {}
    for cat in BOTTLENECK_CATEGORIES:
        for stream in cat["streams"].values():
            for layer in stream:
                for sym in layer["proxies"]:
                    seen.setdefault(sym)
    return list(seen)


def _rank_layer(layer: dict[str, Any], hist: dict[str, Any]) -> dict[str, Any]:
    """Score each layer by the recent momentum of its proxy tickers."""
    proxies = layer["proxies"]
    pct_sum = 0.0
    n = 0
    detail = {}
    for sym in proxies:
        h = hist.get(sym)
        if not h:
            h = market.get_history(sym, days=120)
        if not h:
            continue
        # Keep valid 0.0 closes; drop only missing/NaN values. (This filter is
        # deliberately stricter than indicators._closes, which keeps NaN.)
        closes = [
            x["close"]
            for x in h
            if x.get("close") is not None and not math.isnan(x["close"])
        ]
        roc = roc_at(closes, config.BOTTLENECK_LOOKBACK_DAYS)
        if roc is None:
            continue
        detail[sym] = round(roc, 1)
        pct_sum += roc
        n += 1
    avg = round(pct_sum / n, 1) if n else None
    return {
        "layer": layer["layer"],
        "why_scarce": layer["why_scarce"],
        "gauge": layer["gauge"],
        "proxies": proxies,
        "proxy_40d_roc_pct": avg,
        "detail": detail,
    }


def _average_score(layers: list[dict[str, Any]]) -> float | None:
    """Average 40d ROC across layers that have a score."""
    values = [layer["proxy_40d_roc_pct"] for layer in layers if layer["proxy_40d_roc_pct"] is not None]
    return round(sum(values) / len(values), 1) if values else None


def _sort_layers(layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by score ascending; None values sink to the bottom."""
    return sorted(layers, key=lambda x: (x["proxy_40d_roc_pct"] is None, x["proxy_40d_roc_pct"] or 0))


def bottleneck_read(snapshot: dict[str, Any]) -> dict[str, Any]:
    hist = snapshot.get("histories", {}).get("extra", {})
    ranked_categories = []
    all_layers = []

    for cat in BOTTLENECK_CATEGORIES:
        stream_data = {}
        for stream_name in ("upstream", "downstream"):
            layers = [_rank_layer(layer, hist) for layer in cat["streams"][stream_name]]
            layers = _sort_layers(layers)
            stream_data[stream_name] = {
                "layers": layers,
                "proxy_40d_roc_pct": _average_score(layers),
            }
            all_layers.extend(layers)
        ranked_categories.append(
            {
                "category": cat["category"],
                "streams": stream_data,
                "proxy_40d_roc_pct": _average_score(
                    stream_data["upstream"]["layers"] + stream_data["downstream"]["layers"]
                ),
            }
        )

    # Strongest single layer across all categories.
    strongest = max(
        (layer for layer in all_layers if layer["proxy_40d_roc_pct"] is not None),
        key=lambda x: x["proxy_40d_roc_pct"],
        default=None,
    )

    return {
        "as_of": snapshot.get("as_of"),
        "framework": "serenity-chokepoint-investing",
        "thesis": (
            "Do not start with the obvious winner. Trace the system architecture "
            "down to the scarce physical input the whole build cannot bypass, and "
            "ask whether that layer is the binding constraint."
        ),
        "categories": ranked_categories,
        "strongest_signal": strongest,
        "note": (
            "Proxy momentum is a rough stress gauge, not a thesis. Each chokepoint "
            "still requires primary-source validation (filings, purchase orders, "
            "qualification evidence) before it becomes an actionable bottleneck."
        ),
    }
