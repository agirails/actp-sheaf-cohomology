"""
Rational arithmetic cross-validation for H¹ computations.

Recomputes all matrix ranks using exact rational arithmetic (fractions.Fraction)
and compares against the floating-point NumPy results and the production
engine. δ₀ is checked for every model; for models with faces, δ₁ is rebuilt
independently, δ₁δ₀ = 0 is checked exactly, and the 2-complex H¹ and H² are
verified from exact ranks. This script validates the claim in the paper that
"all rank computations have been cross-validated using exact rational
arithmetic." Exits 1 on any mismatch.

Usage:
    python3 verify_rational.py
"""

import yaml
import sys
import numpy as np
from fractions import Fraction
from typing import List, Dict


def load_protocol(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_delta0_rational(states: Dict[str, List[str]], transitions: List[dict]):
    """Build coboundary matrix δ₀ using exact Fraction arithmetic."""
    # Compute dimensions
    state_names = sorted(states.keys())
    state_offset = {}
    n_v = 0
    for s in state_names:
        state_offset[s] = n_v
        n_v += len(states[s])

    edge_dims = []
    edge_info = []
    n_e = 0
    for t in transitions:
        src = t["from"]
        tgt = t["to"]
        shared = edge_stalk(states, t)
        edge_info.append({"src": src, "tgt": tgt, "shared": shared, "offset": n_e})
        n_e += len(shared)
        edge_dims.append(len(shared))

    # Build δ₀ with Fraction entries
    delta0 = [[Fraction(0)] * n_v for _ in range(n_e)]

    for t_info in edge_info:
        src = t_info["src"]
        tgt = t_info["tgt"]
        shared = t_info["shared"]
        e_off = t_info["offset"]

        for i, dim_name in enumerate(shared):
            # Target (head) projection: +1
            tgt_idx = state_offset[tgt] + states[tgt].index(dim_name)
            delta0[e_off + i][tgt_idx] += Fraction(1)

            # Source (tail) projection: -1
            src_idx = state_offset[src] + states[src].index(dim_name)
            # Accumulate: on a self-loop src_idx == tgt_idx and the entry is 0.
            delta0[e_off + i][src_idx] -= Fraction(1)

    return delta0, n_v, n_e


def edge_stalk(states: Dict[str, List[str]], t: dict) -> List[str]:
    """Fields on a transition: its ``carries`` list if present, else the shared fields."""
    src, tgt = t["from"], t["to"]
    if t.get("carries") is not None:
        return [d for d in states[src] if d in t["carries"]]
    return [d for d in states[src] if d in states[tgt]]


def build_delta1_rational(states: Dict[str, List[str]], transitions: List[dict], faces: List[dict]):
    """Build coboundary matrix δ₁: C¹ → C² using exact Fraction arithmetic.

    The face stalk is the intersection of the stalks of every edge on the face
    boundary (ordered as in the first boundary edge); each boundary edge maps to
    it by coordinate projection, with sign +1 on ``plus`` and -1 on ``minus``.
    """
    edge_offset, edge_fields, n_e = {}, {}, 0
    for t in transitions:
        edge_offset[t["name"]] = n_e
        edge_fields[t["name"]] = edge_stalk(states, t)
        n_e += len(edge_fields[t["name"]])

    face_rows = []
    for face in faces:
        plus, minus = face.get("plus") or [], face.get("minus") or []
        boundary = plus + minus
        if not boundary:
            continue
        stalk = [d for d in edge_fields[boundary[0]] if all(d in edge_fields[e] for e in boundary[1:])]
        rows = [[Fraction(0)] * n_e for _ in stalk]
        for sign, edges in ((1, plus), (-1, minus)):
            for e in edges:
                for i, d in enumerate(stalk):
                    rows[i][edge_offset[e] + edge_fields[e].index(d)] += Fraction(sign)
        face_rows.extend(rows)

    return face_rows, len(face_rows)


def rational_product_is_zero(a: List[List[Fraction]], b: List[List[Fraction]]) -> bool:
    """True iff the exact product a·b is the zero matrix."""
    if not a or not b:
        return True
    cols = len(b[0])
    for row in a:
        for j in range(cols):
            if sum(row[k] * b[k][j] for k in range(len(b)) if row[k]) != 0:
                return False
    return True


def rational_rank(matrix: List[List[Fraction]]) -> int:
    """Compute rank of a matrix over Q using Gaussian elimination with exact fractions."""
    if not matrix or not matrix[0]:
        return 0

    m = len(matrix)
    n = len(matrix[0])

    # Deep copy
    mat = [[matrix[i][j] for j in range(n)] for i in range(m)]

    rank = 0
    for col in range(n):
        # Find pivot
        pivot_row = None
        for row in range(rank, m):
            if mat[row][col] != 0:
                pivot_row = row
                break

        if pivot_row is None:
            continue

        # Swap
        mat[rank], mat[pivot_row] = mat[pivot_row], mat[rank]

        # Eliminate
        pivot_val = mat[rank][col]
        for row in range(m):
            if row != rank and mat[row][col] != 0:
                factor = mat[row][col] / pivot_val
                for j in range(n):
                    mat[row][j] -= factor * mat[rank][j]

        rank += 1

    return rank


def verify_protocol(yaml_path: str, label: str):
    """Verify a single protocol YAML against numpy results."""
    proto = load_protocol(yaml_path)

    states = {}
    for name, data in proto["states"].items():
        states[name] = data["stalks"]

    transitions = proto.get("transitions", [])
    # Assign names if missing
    for i, t in enumerate(transitions):
        if "name" not in t:
            t["name"] = f"e{i+1}"

    # Rational computation
    delta0_rat, n_v, n_e = build_delta0_rational(states, transitions)
    rank_rational = rational_rank(delta0_rat)
    h1_rational = n_e - rank_rational

    # NumPy computation for comparison
    delta0_np = np.array([[float(x) for x in row] for row in delta0_rat])
    rank_numpy = np.linalg.matrix_rank(delta0_np, tol=1e-9)
    h1_numpy = n_e - rank_numpy

    # Independent check against the production engine's own assembly
    # (dimensions as well as H¹, so a wrong edge stalk cannot hide on a tree).
    import h1_engine
    engine = h1_engine.analyse_protocol(states, transitions)
    h1_engine_val = engine["dim_h1"]

    ok = (rank_rational == rank_numpy) and (h1_engine_val == h1_rational) and (
        (engine["dim_c0"], engine["dim_c1"], engine["rank_delta0"]) == (n_v, n_e, rank_rational)
    )

    print(f"\n{label}")
    print(f"  C⁰ = {n_v}  C¹ = {n_e}   (engine C⁰ = {engine['dim_c0']}  C¹ = {engine['dim_c1']})")
    print(f"  rank(δ₀) rational = {rank_rational}")
    print(f"  rank(δ₀) numpy    = {rank_numpy}")
    print(f"  H¹ rational = {h1_rational}")
    print(f"  H¹ numpy    = {h1_numpy}")
    print(f"  H¹ engine   = {h1_engine_val}")

    faces = proto.get("faces") or []
    if faces:
        delta1_rat, n_f = build_delta1_rational(states, transitions, faces)
        complex_ok = rational_product_is_zero(delta1_rat, delta0_rat)
        rank1_rational = rational_rank(delta1_rat)
        delta1_np = np.array([[float(x) for x in row] for row in delta1_rat]).reshape(n_f, n_e)
        rank1_numpy = np.linalg.matrix_rank(delta1_np, tol=1e-9) if n_f and n_e else 0
        h1_2c = (n_e - rank1_rational) - rank_rational
        h2_2c = n_f - rank1_rational
        two = h1_engine.analyse_protocol_2complex(states, transitions, faces)
        ok_2c = complex_ok and rank1_rational == rank1_numpy and (
            (two["dim_c2"], two["rank_delta1"], two["dim_h1"], two["dim_h2"])
            == (n_f, rank1_rational, h1_2c, h2_2c)
        )
        ok = ok and ok_2c
        print(f"  2-complex: {len(faces)} faces  C² = {n_f}   (engine C² = {two['dim_c2']})")
        print(f"  δ₁δ₀ = 0 exactly: {complex_ok}")
        print(f"  rank(δ₁) rational = {rank1_rational}")
        print(f"  rank(δ₁) numpy    = {rank1_numpy}")
        print(f"  rank(δ₁) engine   = {two['rank_delta1']}")
        print(f"  2-complex H¹ rational = {h1_2c}  engine = {two['dim_h1']}")
        print(f"  2-complex H² rational = {h2_2c}  engine = {two['dim_h2']}")

    print(f"  {'✅' if ok else '❌ MISMATCH'}")

    return ok


if __name__ == "__main__":
    print("RATIONAL ARITHMETIC CROSS-VALIDATION")
    print("=" * 50)

    results = []

    results.append(verify_protocol("protocol_paper_v1.yaml", "ACTP v2.7 (paper model, protocol_paper_v1.yaml)"))
    results.append(verify_protocol("protocol.yaml", "ACTP v2.7 (current kernel model, protocol.yaml)"))
    results.append(verify_protocol("toy_escrow_protocol.yaml", "Toy escrow (3-state, no cycle)"))
    results.append(verify_protocol("toy_escrow_broken.yaml", "Toy escrow broken (4-state, with cycle)"))

    print("\n" + "=" * 50)
    if all(results):
        print("ALL CROSS-VALIDATIONS PASSED ✅")
        print("Rational arithmetic agrees with floating-point in every case.")
    else:
        print("❌ CROSS-VALIDATION FAILED — investigate mismatches above.")
        sys.exit(1)
