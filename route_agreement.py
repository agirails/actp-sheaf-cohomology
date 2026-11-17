#!/usr/bin/env python3
"""Route agreement: a sheaf whose maps carry the accounting.

The H^1 linter (h1_engine.py) uses restriction maps that only pick out shared
field names, so its cohomology counts loops per field. This module uses maps
that say HOW each promised quantity is computed across a transition. Its global
sections then mean something about the protocol:

    THEOREM (route agreement). Let every state be reachable from the initial
    state r. Evaluation at r identifies H^0 with the agreement subspace
        A = { a in V_r : T_p a = T_q a for all directed routes p, q from r
              that end in the same state },
    so dim H^0 = dim V_r exactly when every two routes agree on every promised
    quantity, and dim V_r - dim H^0 counts the independent parameter directions
    on which some pair of routes disagrees. A is cut out by one linear condition
    per non-tree transition of any spanning arborescence, so each failure names
    a loop.

Proof and scope: ROUTE_AGREEMENT.md. All arithmetic is exact (fractions).

Model format (YAML):

    initial: COMMITTED
    states:
      COMMITTED: {quantities: [amount]}
      SETTLED:   {quantities: [provider, fee, vault]}
    transitions:
      - name: settle
        from: COMMITTED
        to: SETTLED
        map:                       # target quantity <- linear form in source quantities
          provider: {amount: 99/100}
          fee:      {amount: 1/100}
          # a target quantity with no entry is 0
    views:                         # optional: who can observe which quantities
      provider_party: [provider]

Only quantities the protocol PROMISES are a function of the state alone belong
in `quantities`. A value that legitimately differs by route (a dispute split)
must be a named free quantity at the state where it is chosen.
"""
from __future__ import annotations

import sys
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

Matrix = List[List[Fraction]]


class ModelError(ValueError):
    """The model is malformed or outside the theorem's scope."""


# --------------------------------------------------------------- exact linear algebra

def _rank(rows: Matrix) -> int:
    m = [r[:] for r in rows]
    rank, cols = 0, (len(m[0]) if m else 0)
    for c in range(cols):
        p = next((i for i in range(rank, len(m)) if m[i][c] != 0), None)
        if p is None:
            continue
        m[rank], m[p] = m[p], m[rank]
        piv = m[rank][c]
        m[rank] = [x / piv for x in m[rank]]
        for i in range(len(m)):
            if i != rank and m[i][c] != 0:
                f = m[i][c]
                m[i] = [a - f * b for a, b in zip(m[i], m[rank])]
        rank += 1
    return rank


def _matmul(a: Matrix, b: Matrix, cols: int) -> Matrix:
    """a (rows x k) times b (k x cols). `cols` is passed explicitly so that a zero-dimensional
    middle or outer space still yields a correctly shaped (possibly all-zero) matrix."""
    return [[sum((a[i][k] * b[k][j] for k in range(len(b))), Fraction(0)) for j in range(cols)]
            for i in range(len(a))]


def _identity(n: int) -> Matrix:
    return [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]


# --------------------------------------------------------------- model

class Model:
    def __init__(self, cfg: dict):
        if not isinstance(cfg, dict) or "states" not in cfg or "transitions" not in cfg:
            raise ModelError("model needs 'states' and 'transitions'")
        self.name = cfg.get("name", "")
        self.quantities: Dict[str, List[str]] = {}
        for s, body in cfg["states"].items():
            qs = list((body or {}).get("quantities") or [])
            if len(set(qs)) != len(qs):
                raise ModelError(f"state {s}: duplicate quantity")
            self.quantities[s] = qs
        self.transitions: List[dict] = []
        seen = set()
        for t in cfg["transitions"]:
            for k in ("name", "from", "to"):
                if k not in t:
                    raise ModelError(f"transition missing '{k}': {t}")
            if t["name"] in seen:
                raise ModelError(f"duplicate transition name {t['name']}")
            seen.add(t["name"])
            for end in (t["from"], t["to"]):
                if end not in self.quantities:
                    raise ModelError(f"transition {t['name']}: unknown state {end}")
            self.transitions.append({"name": t["name"], "from": t["from"], "to": t["to"],
                                     "matrix": self._matrix(t)})
        self.initial = cfg.get("initial")
        if self.initial is None:
            targets = {t["to"] for t in self.transitions if t["from"] != t["to"]}
            roots = [s for s in self.quantities if s not in targets]
            if len(roots) != 1:
                raise ModelError(f"cannot infer a single initial state (candidates: {roots}); set 'initial:'")
            self.initial = roots[0]
        if self.initial not in self.quantities:
            raise ModelError(f"unknown initial state {self.initial}")
        self.views: Dict[str, List[str]] = {k: list(v) for k, v in (cfg.get("views") or {}).items()}

    def _matrix(self, t: dict) -> Matrix:
        src, dst = self.quantities[t["from"]], self.quantities[t["to"]]
        spec = t.get("map") or {}
        for q in spec:
            if q not in dst:
                raise ModelError(f"transition {t['name']}: '{q}' is not a quantity of {t['to']}")
        rows = []
        for q in dst:
            form = spec.get(q) or {}
            for s in form:
                if s not in src:
                    raise ModelError(f"transition {t['name']}: '{s}' is not a quantity of {t['from']}")
            rows.append([Fraction(str(form.get(s, 0))) for s in src])
        return rows

    def dim(self, s: str) -> int:
        return len(self.quantities[s])


def load(path: str) -> Model:
    import yaml
    with open(path, encoding="utf-8") as f:
        return Model(yaml.safe_load(f))


# --------------------------------------------------------------- cohomology, computed directly

def coboundary(m: Model) -> Matrix:
    """delta: C^0 -> C^1, (delta x)_e = T_e x_u - x_v, with the edge stalk V_v."""
    off, n = {}, 0
    for s in m.quantities:
        off[s] = n
        n += m.dim(s)
    rows = []
    for t in m.transitions:
        u, v, T = t["from"], t["to"], t["matrix"]
        for i in range(m.dim(v)):
            row = [Fraction(0)] * n
            for j in range(m.dim(u)):
                row[off[u] + j] += T[i][j]
            row[off[v] + i] -= 1
            rows.append(row)
    return rows


def cohomology(m: Model) -> Tuple[int, int]:
    """(dim H^0, dim H^1) from the coboundary matrix alone."""
    d = coboundary(m)
    c0 = sum(m.dim(s) for s in m.quantities)
    c1 = len(d)
    r = _rank(d) if d else 0
    return c0 - r, c1 - r


# --------------------------------------------------------------- route agreement, computed by routes

def analyse(m: Model) -> dict:
    """Agreement subspace via a spanning arborescence, with one finding per disagreeing loop.

    Independent of `cohomology`: the two must agree on dim H^0 (that equality is the theorem;
    tests/test_route_agreement.py checks it on random models)."""
    r = m.initial
    out: Dict[str, List[dict]] = {}
    for t in m.transitions:
        out.setdefault(t["from"], []).append(t)

    # Breadth-first arborescence: tree_map[v] = T along the tree route r -> v.
    tree_map: Dict[str, Matrix] = {r: _identity(m.dim(r))}
    tree_route: Dict[str, List[str]] = {r: []}
    tree_edges = set()
    queue = [r]
    while queue:
        u = queue.pop(0)
        for t in out.get(u, []):
            v = t["to"]
            if v in tree_map:
                continue
            tree_map[v] = _matmul(t["matrix"], tree_map[u], m.dim(r))
            tree_route[v] = tree_route[u] + [t["name"]]
            tree_edges.add(t["name"])
            queue.append(v)
    unreachable = [s for s in m.quantities if s not in tree_map]
    if unreachable:
        raise ModelError(f"states not reachable from {r}: {unreachable} (outside the theorem's scope)")

    findings, stacked = [], []
    for t in m.transitions:
        if t["name"] in tree_edges:
            continue
        u, v = t["from"], t["to"]
        via = _matmul(t["matrix"], tree_map[u], m.dim(r))
        diff = [[a - b for a, b in zip(ra, rb)] for ra, rb in zip(via, tree_map[v])]
        rank = _rank(diff) if diff and m.dim(r) else 0
        if rank == 0:
            continue
        stacked += diff
        bad = [q for q, row in zip(m.quantities[v], diff) if any(x != 0 for x in row)]
        findings.append({
            "state": v,
            "route_a": tree_route[v],
            "route_b": tree_route[u] + [t["name"]],
            "rank": rank,
            "quantities": bad,
            "difference": {q: {s: row[j] for j, s in enumerate(m.quantities[r]) if row[j] != 0}
                           for q, row in zip(m.quantities[v], diff) if any(x != 0 for x in row)},
            "seen_by": sorted(name for name, qs in m.views.items() if set(qs) & set(bad)),
            "not_seen_by": sorted(name for name, qs in m.views.items() if not set(qs) & set(bad)),
        })
    dim_r = m.dim(r)
    dim_a = dim_r - (_rank(stacked) if stacked else 0)
    h0, h1 = cohomology(m)
    return {
        "initial": r,
        "free_parameters": dim_r,
        "agreement_dim": dim_a,
        "h0": h0,
        "h1": h1,
        "routes_agree": dim_a == dim_r,
        "theorem_holds": h0 == dim_a,
        # Corollary 4: dim H^1 = (sum of head-stalk dims over non-tree transitions) - (dim V_r - dim H^0)
        "h1_by_corollary": sum(m.dim(t["to"]) for t in m.transitions if t["name"] not in tree_edges)
                           - (dim_r - dim_a),
        "findings": findings,
    }


def evaluate(m: Model, route: List[str], initial_values: Dict[str, object]) -> Dict[str, Fraction]:
    """Carry concrete initial values along a named route; returns the final state's quantities."""
    by_name = {t["name"]: t for t in m.transitions}
    state = m.initial
    vec = [[Fraction(str(initial_values.get(q, 0)))] for q in m.quantities[state]]
    for name in route:
        t = by_name[name]
        if t["from"] != state:
            raise ModelError(f"route breaks at {name}: at {state}, transition leaves {t['from']}")
        vec = _matmul(t["matrix"], vec, 1)
        state = t["to"]
    return {q: row[0] for q, row in zip(m.quantities[state], vec)}


# --------------------------------------------------------------- CLI

def _fmt(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Route-agreement check for an accounting model.")
    ap.add_argument("--config", required=True)
    args = ap.parse_args(argv)
    try:
        m = load(args.config)
        res = analyse(m)
    except ModelError as e:
        print(f"MODEL ERROR: {e}")
        return 2
    print(f"model: {m.name or args.config}   initial state: {res['initial']}")
    print(f"free parameters (dim V_r) = {res['free_parameters']}   dim H^0 = {res['h0']}   dim H^1 = {res['h1']}")
    if not res["theorem_holds"]:
        print("INTERNAL ERROR: dim H^0 differs from the agreement dimension")
        return 3
    if res["routes_agree"]:
        print("ROUTES AGREE: every route gives the same promised quantities.")
        return 0
    print(f"ROUTES DISAGREE on {res['free_parameters'] - res['agreement_dim']} parameter direction(s):")
    for f in res["findings"]:
        print(f"  at {f['state']}: route {' > '.join(f['route_a']) or '(start)'}")
        print(f"       versus route {' > '.join(f['route_b'])}")
        for q, form in f["difference"].items():
            terms = " + ".join(f"({_fmt(c)})*{s}" for s, c in form.items())
            print(f"    {q}: second route minus first = {terms}")
        if f["seen_by"] or f["not_seen_by"]:
            print(f"    visible to: {', '.join(f['seen_by']) or 'nobody listed'}"
                  f"   not visible to: {', '.join(f['not_seen_by']) or 'nobody listed'}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
