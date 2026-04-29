"""
Rational arithmetic cross-validation for H¹ computations.

Recomputes all matrix ranks using exact rational arithmetic (fractions.Fraction)
and compares against the floating-point NumPy results. This script validates
the claim in the paper that "all rank computations have been cross-validated
using exact rational arithmetic."

Usage:
    python3 verify_rational.py
"""

import yaml
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
        shared = [d for d in states[src] if d in states[tgt]]
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
            delta0[e_off + i][tgt_idx] = Fraction(1)

            # Source (tail) projection: -1
            src_idx = state_offset[src] + states[src].index(dim_name)
            delta0[e_off + i][src_idx] = Fraction(-1)

    return delta0, n_v, n_e


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

    match = "✅" if rank_rational == rank_numpy else "❌ MISMATCH"

    print(f"\n{label}")
    print(f"  C⁰ = {n_v}  C¹ = {n_e}")
    print(f"  rank(δ₀) rational = {rank_rational}")
    print(f"  rank(δ₀) numpy    = {rank_numpy}")
    print(f"  H¹ rational = {h1_rational}")
    print(f"  H¹ numpy    = {h1_numpy}")
    print(f"  {match}")

    return rank_rational == rank_numpy


if __name__ == "__main__":
    print("RATIONAL ARITHMETIC CROSS-VALIDATION")
    print("=" * 50)

    results = []

    results.append(verify_protocol("protocol.yaml", "ACTP v2.7 (main protocol)"))
    results.append(verify_protocol("toy_escrow_protocol.yaml", "Toy escrow (3-state, no cycle)"))
    results.append(verify_protocol("toy_escrow_broken.yaml", "Toy escrow broken (4-state, with cycle)"))

    print("\n" + "=" * 50)
    if all(results):
        print("ALL CROSS-VALIDATIONS PASSED ✅")
        print("Rational arithmetic agrees with floating-point in every case.")
    else:
        print("❌ CROSS-VALIDATION FAILED — investigate mismatches above.")
