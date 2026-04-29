"""
H¹ Sheaf Cohomology Engine
===========================
Core computation module extracted from actp_sheaf.py.
Accepts arbitrary state machine definitions (from YAML) and computes H¹.

No hardcoded ACTP states — fully generic.
"""

import numpy as np
from typing import Dict, List, Optional


def build_restriction_maps(
    states: Dict[str, List[str]],
    transitions: List[dict],
) -> dict:
    """
    Build restriction maps for each transition.

    Args:
        states: {state_name: [dimension_names]}
        transitions: [{from, to, name}]

    Returns:
        dict of transition_name -> {shared, source_proj, target_proj}
    """
    restrictions = {}

    for t in transitions:
        source = t["from"]
        target = t["to"]
        name = t["name"]

        source_dims = states[source]
        target_dims = states[target]
        shared = [d for d in source_dims if d in target_dims]

        if not shared:
            restrictions[name] = {
                "shared": [],
                "source_proj": np.zeros((0, len(source_dims))),
                "target_proj": np.zeros((0, len(target_dims))),
            }
            continue

        source_proj = np.zeros((len(shared), len(source_dims)))
        target_proj = np.zeros((len(shared), len(target_dims)))

        for i, dim_name in enumerate(shared):
            source_proj[i, source_dims.index(dim_name)] = 1.0
            target_proj[i, target_dims.index(dim_name)] = 1.0

        restrictions[name] = {
            "shared": shared,
            "source_proj": source_proj,
            "target_proj": target_proj,
        }

    return restrictions


def build_face_maps(
    restrictions: dict,
    faces: List[dict],
) -> dict:
    """
    Build restriction maps from edge stalks to face stalks.

    Each face is defined as a pair of directed paths with the same endpoints:
      {name, plus: [edge, ...], minus: [edge, ...]}

    The face stalk is the ordered intersection of all edge stalks appearing in
    the boundary. Each incident edge restricts to the face via coordinate
    projection onto those shared dimensions.
    """
    face_maps = {}

    for face in faces:
        plus = face.get("plus", [])
        minus = face.get("minus", [])
        boundary_edges = plus + minus

        if not boundary_edges:
            face_maps[face["name"]] = {
                "shared": [],
                "edge_proj": {},
                "plus": plus,
                "minus": minus,
            }
            continue

        ordered_reference = restrictions[boundary_edges[0]]["shared"]
        shared_sets = [set(restrictions[edge]["shared"]) for edge in boundary_edges[1:]]
        shared = [
            dim_name for dim_name in ordered_reference
            if all(dim_name in shared_set for shared_set in shared_sets)
        ]

        edge_proj = {}
        for edge in boundary_edges:
            edge_dims = restrictions[edge]["shared"]
            proj = np.zeros((len(shared), len(edge_dims)))
            for i, dim_name in enumerate(shared):
                proj[i, edge_dims.index(dim_name)] = 1.0
            edge_proj[edge] = proj

        face_maps[face["name"]] = {
            "shared": shared,
            "edge_proj": edge_proj,
            "plus": plus,
            "minus": minus,
        }

    return face_maps


def build_coboundary_0(
    states: Dict[str, List[str]],
    transitions: List[dict],
    restrictions: dict,
) -> np.ndarray:
    """
    Build δ₀: C⁰ → C¹.
    """
    state_names = sorted(states.keys())
    vertex_dims = {s: len(states[s]) for s in state_names}
    vertex_offsets = {}
    offset = 0
    for s in state_names:
        vertex_offsets[s] = offset
        offset += vertex_dims[s]
    total_c0 = offset

    edge_offsets = {}
    offset = 0
    for t in transitions:
        name = t["name"]
        d = len(restrictions[name]["shared"])
        edge_offsets[name] = offset
        offset += d
    total_c1 = offset

    if total_c0 == 0 or total_c1 == 0:
        return np.zeros((total_c1, total_c0))

    delta_0 = np.zeros((total_c1, total_c0))

    for t in transitions:
        source = t["from"]
        target = t["to"]
        name = t["name"]
        r = restrictions[name]
        shared_dim = len(r["shared"])
        if shared_dim == 0:
            continue

        e_off = edge_offsets[name]
        s_off = vertex_offsets[source]
        t_off = vertex_offsets[target]

        delta_0[e_off:e_off + shared_dim, t_off:t_off + vertex_dims[target]] += r["target_proj"]
        delta_0[e_off:e_off + shared_dim, s_off:s_off + vertex_dims[source]] -= r["source_proj"]

    return delta_0


def build_coboundary_1(
    transitions: List[dict],
    restrictions: dict,
    faces: List[dict],
    face_maps: dict,
) -> np.ndarray:
    """
    Build δ₁: C¹ → C² from explicit face boundaries.
    """
    edge_offsets = {}
    offset = 0
    for t in transitions:
        name = t["name"]
        d = len(restrictions[name]["shared"])
        edge_offsets[name] = offset
        offset += d
    total_c1 = offset

    face_offsets = {}
    offset = 0
    for face in faces:
        name = face["name"]
        d = len(face_maps[name]["shared"])
        face_offsets[name] = offset
        offset += d
    total_c2 = offset

    if total_c1 == 0 or total_c2 == 0:
        return np.zeros((total_c2, total_c1))

    delta_1 = np.zeros((total_c2, total_c1))

    for face in faces:
        name = face["name"]
        f = face_maps[name]
        face_dim = len(f["shared"])
        if face_dim == 0:
            continue

        f_off = face_offsets[name]

        for edge in f["plus"]:
            e_off = edge_offsets[edge]
            e_dim = len(restrictions[edge]["shared"])
            delta_1[f_off:f_off + face_dim, e_off:e_off + e_dim] += f["edge_proj"][edge]

        for edge in f["minus"]:
            e_off = edge_offsets[edge]
            e_dim = len(restrictions[edge]["shared"])
            delta_1[f_off:f_off + face_dim, e_off:e_off + e_dim] -= f["edge_proj"][edge]

    return delta_1


def compute_h1(delta_0: np.ndarray) -> dict:
    """
    Compute H¹ = C¹ / im(δ₀) for a graph complex (no 2-cells).
    """
    dim_c1, dim_c0 = delta_0.shape
    rank = int(np.linalg.matrix_rank(delta_0, tol=1e-10))
    dim_h0 = dim_c0 - rank
    dim_h1 = dim_c1 - rank

    return {
        "dim_c0": dim_c0,
        "dim_c1": dim_c1,
        "rank_delta0": rank,
        "dim_h0": dim_h0,
        "dim_h1": dim_h1,
        "euler": dim_h0 - dim_h1,
    }


def compute_h1_2complex(delta_0: np.ndarray, delta_1: np.ndarray) -> dict:
    """
    Compute H• for a 2-complex.
    """
    dim_c1, dim_c0 = delta_0.shape
    dim_c2 = delta_1.shape[0]
    rank_delta0 = int(np.linalg.matrix_rank(delta_0, tol=1e-10))
    rank_delta1 = int(np.linalg.matrix_rank(delta_1, tol=1e-10))
    dim_ker_delta1 = dim_c1 - rank_delta1

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        composition = delta_1 @ delta_0
    if composition.size and np.all(np.isfinite(composition)):
        complex_residual = float(np.max(np.abs(composition)))
    elif composition.size:
        complex_residual = float("inf")
    else:
        complex_residual = 0.0

    return {
        "dim_c0": dim_c0,
        "dim_c1": dim_c1,
        "dim_c2": dim_c2,
        "rank_delta0": rank_delta0,
        "rank_delta1": rank_delta1,
        "dim_ker_delta1": dim_ker_delta1,
        "dim_h0": dim_c0 - rank_delta0,
        "dim_h1": dim_ker_delta1 - rank_delta0,
        "dim_h2": dim_c2 - rank_delta1,
        "euler": (dim_c0 - rank_delta0) - (dim_ker_delta1 - rank_delta0) + (dim_c2 - rank_delta1),
        "complex_residual": complex_residual,
    }


def analyse_protocol(
    states: Dict[str, List[str]],
    transitions: List[dict],
) -> dict:
    """
    Full H¹ analysis of a protocol definition.

    Returns:
        {dim_c0, dim_c1, rank_delta0, dim_h0, dim_h1, euler}
    """
    restrictions = build_restriction_maps(states, transitions)
    delta_0 = build_coboundary_0(states, transitions, restrictions)
    return compute_h1(delta_0)


def analyse_protocol_2complex(
    states: Dict[str, List[str]],
    transitions: List[dict],
    faces: List[dict],
) -> dict:
    """
    Full cohomology analysis of an explicit 2-complex refinement.
    """
    restrictions = build_restriction_maps(states, transitions)
    face_maps = build_face_maps(restrictions, faces)
    delta_0 = build_coboundary_0(states, transitions, restrictions)
    delta_1 = build_coboundary_1(transitions, restrictions, faces, face_maps)
    result = compute_h1_2complex(delta_0, delta_1)
    result["faces"] = [
        {
            "name": face["name"],
            "dim": len(face_maps[face["name"]]["shared"]),
            "plus": face.get("plus", []),
            "minus": face.get("minus", []),
        }
        for face in faces
    ]
    return result


def analyse_path(
    states: Dict[str, List[str]],
    transitions: List[dict],
    path_states: List[str],
) -> dict:
    """
    Compute H¹ for a subgraph defined by a set of states.
    Only includes transitions where both endpoints are in path_states.
    """
    path_set = set(path_states)
    sub_states = {s: states[s] for s in path_states if s in states}
    sub_transitions = [
        t for t in transitions
        if t["from"] in path_set and t["to"] in path_set
    ]

    if not sub_states or not sub_transitions:
        total_dims = sum(len(v) for v in sub_states.values())
        return {
            "dim_c0": total_dims,
            "dim_c1": 0,
            "rank_delta0": 0,
            "dim_h0": total_dims,
            "dim_h1": 0,
            "euler": total_dims,
        }

    return analyse_protocol(sub_states, sub_transitions)


def trace_leaks(
    states: Dict[str, List[str]],
    transitions: List[dict],
    path_states: Optional[List[str]] = None,
) -> List[dict]:
    """
    Identify exactly which dimensions are lost at each transition.

    Returns list of:
        {from, to, name, lost_from_source, lost_from_target, shared}
    """
    if path_states:
        path_set = set(path_states)
        transitions = [
            t for t in transitions
            if t["from"] in path_set and t["to"] in path_set
        ]

    leaks = []
    for t in transitions:
        source = t["from"]
        target = t["to"]
        source_dims = set(states.get(source, []))
        target_dims = set(states.get(target, []))
        shared = source_dims & target_dims

        lost_from_source = sorted(source_dims - target_dims)
        lost_from_target = sorted(target_dims - source_dims)

        if lost_from_source or lost_from_target:
            leaks.append({
                "from": source,
                "to": target,
                "name": t["name"],
                "shared": sorted(shared),
                "lost_from_source": lost_from_source,
                "gained_at_target": lost_from_target,
                "shared_count": len(shared),
                "source_total": len(source_dims),
                "target_total": len(target_dims),
            })

    return leaks
