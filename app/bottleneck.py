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
# upstream (scarce physical inputs / enablers) and downstream (end-product
# builders / deployers). Tickers are chosen as: major players, standout
# mid/small caps, and ETFs that cover the rest of a layer. Categories are
# kept in a fixed presentation order.
#
# Chain fluency (per the serenity framework): every upstream layer names the
# distinct physical role it plays (raw material / substrate / epi / foundry /
# laser array / external light source / light engine / silicon-photonics
# platform / pluggable transceiver / LRO/LPO / CPO / package-test / EMS /
# power semiconductor / transformer / CDU / IPP). The visible assembler may
# reprice first; the durable profit pool usually sits at the scarcer layer.
BOTTLENECK_CATEGORIES = [
    {
        "category": "Agentic AI",
        "streams": {
            "upstream": [
                {
                    "layer": "Compute / accelerator silicon",
                    "proxies": ["NVDA", "AMD", "AVGO", "MRVL", "QCOM", "ARM", "CRDO", "ALAB"],
                    "gauge": "Accelerator availability, ASIC ramp commentary, custom-silicon design wins",
                    "why_scarce": "Training and inference agents require specialized silicon; merchant and hyperscaler ASICs both pull on the same advanced-node capacity",
                },
                {
                    "layer": "Leading-edge foundry (EUV / advanced node)",
                    "proxies": ["TSM", "ASML"],
                    "gauge": "Foundry utilization, EUV tool shipments, advanced-node pricing",
                    "why_scarce": "3nm/2nm leading-edge wafer capacity is a single-vendor bottleneck — every accelerator and mobile SoC funnels through it",
                },
                {
                    "layer": "Advanced packaging / CoWoS / substrate",
                    "proxies": ["TSM", "AMAT", "KLAC", "LRCX", "ONTO", "FORM"],
                    "gauge": "CoWoS slot allocation, glass-core substrate ramps, packaging yield",
                    "why_scarce": "CoWoS / advanced-packaging capacity is the single shared substrate for high-end AI accelerators and the new binding layer behind foundry",
                },
                {
                    "layer": "HBM / DRAM / NAND memory",
                    "proxies": ["MU", "005930.KS", "000660.KS", "SNDK", "STX", "WDC"],
                    "gauge": "HBM sold-out status, DRAM/NAND pricing, capacity additions",
                    "why_scarce": "HBM capacity sets the ceiling on accelerator shipments; data-center DRAM/NAND pricing power is unusually concentrated",
                },
                {
                    "layer": "Optical transceivers / pluggable modules",
                    "proxies": ["AAOI", "CIEN", "LITE", "COHR"],
                    "gauge": "800G/1.6T lead times, EML/CW laser supply locks, 1.6T volume orders",
                    "why_scarce": "Each speed transition re-prices the qualified laser / module supplier; visible optics is the canary for the rack-scale fabric",
                },
                {
                    "layer": "Silicon-photonics platform / CPO",
                    "proxies": ["MRVL", "AVGO", "LITE", "COHR"],
                    "gauge": "NVLink Fusion ecosystem adds, CPO design-ins, foundry platform validation",
                    "why_scarce": "CPO moves laser and switching onto the package; the silicon-photonics platform is the architecture pivot and a separate evidence layer",
                },
                {
                    "layer": "Optical EMS / package & test",
                    "proxies": ["FN"],
                    "gauge": "Backlog from named customers (Lumentum, NVIDIA), advanced-packaging capacity",
                    "why_scarce": "Advanced optical packaging is concentrated in a few EMS partners — they are the bottleneck even when the laser / chip supply loosens",
                },
                {
                    "layer": "Switch silicon / rack-scale fabric",
                    "proxies": ["AVGO", "MRVL", "ANET", "CRDO"],
                    "gauge": "Custom-silicon ramps, 51.2T/102.4T switch launches, optics attach",
                    "why_scarce": "Rack-scale optical fabrics need custom switch silicon and qualified retimers/AEC; this is the connective tissue of the AI cluster",
                },
                {
                    "layer": "Power semis (SiC / GaN) for data-center delivery",
                    "proxies": ["ON", "NVMI", "TXN", "MPWR"],
                    "gauge": "SiC wafer supply, 800V DC architecture adoption, GaN power-module ramps",
                    "why_scarce": "800V DC architectures need SiC/GaN; SiC substrate and qualified device suppliers are concentrated and scaling slowly",
                },
            ],
            "downstream": [
                {
                    "layer": "Hyperscaler cloud platforms",
                    "proxies": ["MSFT", "GOOGL", "AMZN", "META", "ORCL"],
                    "gauge": "Capex guidance, AI revenue run-rates, capacity buildout pace",
                    "why_scarce": "They monetize agentic AI at scale and set the capex tone for the whole stack",
                },
                {
                    "layer": "Agentic AI applications",
                    "proxies": ["PLTR", "CRM", "NOW", "SHOP", "ADBE", "SNOW", "DDOG", "CRWD", "NET", "WDAY"],
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
                    "proxies": ["MU", "SNDK", "WDC", "STX"],
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
        "category": "Power / data-center infrastructure",
        "streams": {
            "upstream": [
                {
                    "layer": "Gas turbines (OEM) — three-maker oligopoly",
                    "proxies": ["GEV"],
                    "gauge": "Backlog (GEV ~110 GW target), HA-turbine slot pricing, new-unit deliveries",
                    "why_scarce": "GE Vernova / Siemens Energy / Mitsubishi hold >90% of utility-scale gas-turbine slots through 2030; new heavy-duty deliveries quote out 5+ years",
                },
                {
                    "layer": "Transformers / switchgear / grid electricals",
                    "proxies": ["ETN", "PWR", "NVT"],
                    "gauge": "DC-related backlog growth, book-to-bill, distribution-spec wins",
                    "why_scarce": "Utility-scale transformers are 2–4 year lead-time items; the constraint sits in copper + steel + skilled labor, not in the OEM brand",
                },
                {
                    "layer": "In-rack power / liquid cooling / CDU",
                    "proxies": ["VRT", "ETN"],
                    "gauge": "CDU design-ins at hyperscalers, NVIDIA-collaboration revenue, liquid-cooling attach",
                    "why_scarce": "100+ kW racks need liquid cooling; CDU capacity and qualified thermal suppliers are scarce relative to accelerator build",
                },
                {
                    "layer": "Behind-the-meter generation (fuel cells)",
                    "proxies": ["BE"],
                    "gauge": "Total backlog, signed hyperscaler offtake, SOFC delivery cadence",
                    "why_scarce": "Fuel cells are the only near-term path to bypass grid interconnection; moat is speed-to-power, contestable as capacity scales",
                },
                {
                    "layer": "Independent power producers (nuclear / gas)",
                    "proxies": ["CEG", "VST", "TLN", "NRG"],
                    "gauge": "Signed hyperscaler PPAs, PJM/ERCOT capacity prices, nuclear PTC floor",
                    "why_scarce": "Existing nuclear capacity is a scarce, regulated, 24/7 baseload asset; new nuclear cannot be built on AI's timeline",
                },
                {
                    "layer": "Data-center real estate / colo",
                    "proxies": ["EQIX", "DLR", "PLD"],
                    "gauge": "Wholesale lease rates, MW deliverable, power-secured land bank",
                    "why_scarce": "Secured power + interconnect queue position are the moat; speculative colo without power-secured land does not scale",
                },
            ],
            "downstream": [
                {
                    "layer": "Hyperscaler / cloud-platform deployers",
                    "proxies": ["MSFT", "GOOGL", "AMZN", "META", "ORCL"],
                    "gauge": "Capex guidance, AI revenue run-rate, signed long-term PPAs",
                    "why_scarce": "They are the price-setting buyer for upstream power + cooling + colo; their build pace defines the binding constraint",
                },
                {
                    "layer": "Neocloud / GPU-cluster operators",
                    "proxies": ["CRWV", "NBIS", "APLD", "DELL", "HPE", "SMCI", "ANET"],
                    "gauge": "Contracted ARR, customer concentration, financing quality, named hyperscaler offtake",
                    "why_scarce": "Contracted GPU cluster capacity with power, financing, and customer contracts is scarce and lumpy; counterparty quality separates durable ARR from vapor",
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
