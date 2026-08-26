"""
ml/network_engine.py

Simulated social-network graph generation engine.

Produces:
  - nodes  : users/entities with community labels and influence scores
  - edges  : connections (follows, mentions, shares, replies)
  - communities : cluster summaries
  - propagation : step-by-step information/topic/sentiment spread path
  - influencers : ranked list with multi-dimensional influence scores

Influence scoring is inspired by (but simplified from):
  - Degree centrality   (raw connection count)
  - Betweenness proxy   (hub role in bridging communities)
  - PageRank-style score (weighted by neighbour influence)

Future replacement: networkx + real graph data + proper PageRank.
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Community & persona data
# ---------------------------------------------------------------------------

_COMMUNITIES = [
    {"id": 0, "label": "Policy Makers",   "color": "#2563eb"},
    {"id": 1, "label": "Students",        "color": "#7c3aed"},
    {"id": 2, "label": "Educators",       "color": "#059669"},
    {"id": 3, "label": "Tech Enthusiasts","color": "#d97706"},
    {"id": 4, "label": "Media & Press",   "color": "#dc2626"},
    {"id": 5, "label": "NGOs / Advocacy", "color": "#0891b2"},
]

_NODE_PREFIXES = [
    "user_", "handle_", "org_", "media_", "acct_",
]

_NODE_DISPLAY_NAMES = [
    "PolicyHub", "EduVoice", "TechInsight", "YouthConnect", "DataDriven",
    "MediaWatch", "CivicNet", "LearnFirst", "InnovatorsClub", "OpenDebate",
    "GovTracker", "SkillShare", "PressRoom", "AnalystDesk", "AdvocacyNow",
    "FutureScope", "TrendAlert", "PolicyMind", "StemLeague", "NetBridge",
    "DataPulse", "EduHub", "TechRadar", "VoiceForAll", "ImpactNode",
    "CivicPulse", "NarrativeNet", "OutreachX", "InfoFlow", "ConnectIQ",
    "ReachX", "BridgeNode", "CatalystHub", "EchoNet", "ChainLink",
    "SignalX", "CoreNode", "LinkHub", "WebNode", "NexusPoint",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lcg(seed: int) -> int:
    return (seed * 1664525 + 1013904223) & 0xFFFFFFFF


def _drift_f(value: float, tick: int, amplitude: float = 0.05) -> float:
    offset = math.sin(tick * 0.9 + value * 2.1) * amplitude
    return max(0.01, min(0.99, value + offset))


def _drift_i(value: int, tick: int, amplitude: int = 10) -> int:
    offset = int(math.sin(tick * 0.7 + value * 0.4) * amplitude)
    return max(0, value + offset)


# ---------------------------------------------------------------------------
# Graph generation
# ---------------------------------------------------------------------------

def generate_network_graph(
    seed: int,
    tick: int,
    topic: str = "",
    n_nodes: int = 42,
    n_communities: int = 5,
) -> dict[str, Any]:
    """
    Generate a complete network graph suitable for SVG force-simulation.

    Returns:
        nodes       : list of node dicts
        edges       : list of edge dicts
        communities : community metadata
        stats       : aggregate graph statistics
    """
    n_communities = min(n_communities, len(_COMMUNITIES))
    nodes: list[dict[str, Any]] = []
    name_pool = list(_NODE_DISPLAY_NAMES)

    for i in range(n_nodes):
        s = _lcg(seed + i * 13)
        community_id = s % n_communities
        comm = _COMMUNITIES[community_id]

        # Pick unique display name
        name_idx = (s + i) % len(name_pool)
        name = name_pool[name_idx]

        # Base influence ~ hub nodes get higher scores
        is_hub = (i % 7 == 0)
        base_influence = 0.75 + (s % 25) / 100 if is_hub else 0.20 + (s % 50) / 100

        nodes.append({
            "id": i,
            "label": name,
            "community": community_id,
            "community_label": comm["label"],
            "color": comm["color"],
            "influence": round(_drift_f(base_influence, tick + i, 0.04), 3),
            "degree": 0,          # filled in after edge generation
            "is_hub": is_hub,
            # Initial layout positions (force-sim will refine these)
            "x": 350 + int(300 * math.cos(2 * math.pi * i / n_nodes)),
            "y": 250 + int(200 * math.sin(2 * math.pi * i / n_nodes)),
        })

    # ----- edges -----
    edges: list[dict[str, Any]] = []
    edge_set: set[tuple[int, int]] = set()

    # Community-internal edges (dense)
    for i, node in enumerate(nodes):
        s = _lcg(seed + i * 17)
        n_internal = 2 + s % 3
        candidates = [n for n in nodes if n["community"] == node["community"] and n["id"] != i]
        for j in range(min(n_internal, len(candidates))):
            target_id = candidates[(s + j * 7) % len(candidates)]["id"]
            key = (min(i, target_id), max(i, target_id))
            if key not in edge_set:
                edge_set.add(key)
                weight = round(0.4 + (s % 60) / 100, 2)
                edges.append({"source": i, "target": target_id, "weight": weight, "type": "internal"})
                nodes[i]["degree"] += 1
                nodes[target_id]["degree"] += 1

    # Cross-community edges (via hubs)
    hub_ids = [n["id"] for n in nodes if n["is_hub"]]
    for hub_id in hub_ids:
        s = _lcg(seed + hub_id * 29)
        n_cross = 2 + s % 4
        candidates = [n for n in nodes if n["community"] != nodes[hub_id]["community"]]
        for j in range(min(n_cross, len(candidates))):
            target_id = candidates[(s + j * 11) % len(candidates)]["id"]
            key = (min(hub_id, target_id), max(hub_id, target_id))
            if key not in edge_set:
                edge_set.add(key)
                weight = round(0.2 + (s % 40) / 100, 2)
                edges.append({"source": hub_id, "target": target_id, "weight": weight, "type": "cross"})
                nodes[hub_id]["degree"] += 1
                nodes[target_id]["degree"] += 1

    # ----- update influence with degree factor -----
    max_degree = max((n["degree"] for n in nodes), default=1)
    for node in nodes:
        degree_factor = node["degree"] / max_degree
        node["influence"] = round(
            min(0.99, node["influence"] * 0.6 + degree_factor * 0.4), 3
        )

    # ----- community summaries -----
    community_data = []
    for cid in range(n_communities):
        comm_nodes = [n for n in nodes if n["community"] == cid]
        if not comm_nodes:
            continue
        top = max(comm_nodes, key=lambda n: n["influence"])
        community_data.append({
            "id": cid,
            "label": _COMMUNITIES[cid]["label"],
            "color": _COMMUNITIES[cid]["color"],
            "node_count": len(comm_nodes),
            "top_influencer": top["label"],
            "avg_influence": round(sum(n["influence"] for n in comm_nodes) / len(comm_nodes), 3),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "communities": community_data,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "n_communities": n_communities,
            "density": round(len(edges) / max(1, len(nodes) * (len(nodes) - 1) / 2), 4),
        },
    }


# ---------------------------------------------------------------------------
# Influencer ranking
# ---------------------------------------------------------------------------

def generate_influencers(
    seed: int,
    tick: int,
    graph: dict[str, Any],
    top_n: int = 8,
) -> list[dict[str, Any]]:
    """
    Rank nodes by a composite influence score and return top_n.

    Score = 0.4 * normalised_degree + 0.35 * base_influence + 0.25 * hub_bonus
    """
    nodes: list[dict[str, Any]] = graph.get("nodes", [])
    if not nodes:
        return []

    max_degree = max((n["degree"] for n in nodes), default=1)

    ranked = []
    for node in nodes:
        deg_norm = node["degree"] / max_degree
        hub_bonus = 0.15 if node.get("is_hub") else 0.0
        score = 0.4 * deg_norm + 0.35 * node["influence"] + 0.25 * hub_bonus
        score = round(_drift_f(score, tick + node["id"], 0.03), 3)
        ranked.append({
            "rank": 0,
            "name": node["label"],
            "score": score,
            "influence": node["influence"],
            "community": node["community_label"],
            "degree": node["degree"],
            "is_hub": node["is_hub"],
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    for idx, r in enumerate(ranked[:top_n]):
        r["rank"] = idx + 1

    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Information / topic / sentiment spread path
# ---------------------------------------------------------------------------

def generate_propagation_path(
    seed: int,
    tick: int,
    topic: str,
    graph: dict[str, Any],
    steps: int = 5,
) -> list[dict[str, Any]]:
    """
    Generate a conceptual propagation path showing how a topic/sentiment
    spreads from its origin through the network over time.

    Returns a list of propagation steps:
        step, label, description, nodes (list of node IDs), cumulative_reach, pct_reached
    """
    nodes = graph.get("nodes", [])
    communities = graph.get("communities", [])
    total_nodes = max(len(nodes), 1)

    if not communities:
        return []

    # Origin = top influencer (hub with highest influence)
    hubs = sorted([n for n in nodes if n.get("is_hub")], key=lambda n: n["influence"], reverse=True)
    origin = hubs[0] if hubs else nodes[0]

    path = []
    reach_so_far = 0
    node_ids_reached: list[int] = []

    label = topic.strip() or "Topic"

    step_labels = [
        ("Origin",       f'"{label}" emerges from a key source'),
        ("Influencer",   f"Adopted by high-influence node"),
        ("Community A",  "Spreads into primary community"),
        ("Community B",  "Crosses into adjacent community"),
        ("Community C",  "Reaches third community cluster"),
        ("Viral Spread", "Broad propagation across network"),
    ]

    for step_idx in range(min(steps, len(step_labels))):
        s = _lcg(seed + step_idx * 53)

        if step_idx == 0:
            step_nodes = [origin["id"]]
            step_reach = int(total_nodes * 0.02 + s % 5)
        elif step_idx == 1:
            step_nodes = [n["id"] for n in hubs[:3]]
            step_reach = int(total_nodes * 0.08 + s % 8)
        else:
            comm = communities[(step_idx - 2) % len(communities)]
            comm_nodes = [n for n in nodes if n["community"] == comm["id"]]
            step_nodes = [n["id"] for n in comm_nodes[: 4 + s % 4]]
            step_reach = comm["node_count"]

        node_ids_reached.extend(step_nodes)
        reach_so_far = min(total_nodes, reach_so_far + step_reach)
        reach_so_far = _drift_i(reach_so_far, tick + step_idx, 3)

        label_text, desc = step_labels[step_idx]
        path.append({
            "step": step_idx + 1,
            "label": label_text,
            "description": desc,
            "node_ids": list(set(node_ids_reached)),
            "cumulative_reach": reach_so_far,
            "pct_reached": round(reach_so_far / total_nodes * 100, 1),
        })

    return path
