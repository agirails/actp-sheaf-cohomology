"""Tests for route_agreement.py: the theorem checked on random models, and the toy escrow."""
import os
import random
from fractions import Fraction as Fr

import pytest

import route_agreement as ra

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(HERE, "models")


def _load(name):
    return ra.load(os.path.join(MODELS, name))


def _toy(dispute_fee):
    return ra.Model({
        "initial": "COMMITTED",
        "states": {"COMMITTED": {"quantities": ["amount"]}, "DELIVERED": {"quantities": ["amount"]},
                   "DISPUTED": {"quantities": ["amount"]}, "SETTLED": {"quantities": ["paid_out", "fee"]}},
        "transitions": [
            {"name": "deliver", "from": "COMMITTED", "to": "DELIVERED", "map": {"amount": {"amount": 1}}},
            {"name": "settle", "from": "DELIVERED", "to": "SETTLED",
             "map": {"paid_out": {"amount": 1}, "fee": {"amount": "1/100"}}},
            {"name": "dispute", "from": "DELIVERED", "to": "DISPUTED", "map": {"amount": {"amount": 1}}},
            {"name": "uphold", "from": "DISPUTED", "to": "SETTLED",
             "map": {"paid_out": {"amount": 1}, "fee": {"amount": str(dispute_fee)}}},
        ],
    })


# ---------------------------------------------------------------- toy

def test_toy_routes_agree():
    res = ra.analyse(_load("toy_fee_routes.yaml"))
    assert res["routes_agree"] and res["h0"] == 1 and res["findings"] == []


@pytest.mark.parametrize("fee", ["0", "1/200", "999/100000", "1001/100000", "1/50"])
def test_toy_any_other_fee_on_one_route_is_detected(fee):
    res = ra.analyse(_toy(fee))
    assert not res["routes_agree"] and res["h0"] == 0
    assert res["findings"][0]["quantities"] == ["fee"]


def test_toy_same_fee_is_not_flagged():
    """Positive control for the parametrised test above: the equal fee must pass."""
    assert ra.analyse(_toy("1/100"))["routes_agree"]


# ---------------------------------------------------------------- the theorem, on random models

def _random_model(rng, agreeing):
    n = rng.randint(2, 6)
    names = [f"s{i}" for i in range(n)]
    if agreeing:
        # Trivial holonomy by construction: T_e = m_v / m_u for nonzero scalars m.
        dims = {s: 1 for s in names}
        pot = {s: Fr(rng.choice([1, 2, 3, -1, 5]), rng.choice([1, 2, 3])) for s in names}
    else:
        dims = {s: rng.randint(0, 3) for s in names}
        dims[names[0]] = rng.randint(1, 3)
    states = {s: {"quantities": [f"{s}_q{i}" for i in range(dims[s])]} for s in names}
    edges = [(names[rng.randrange(i)], names[i]) for i in range(1, n)]          # reachability
    edges += [(rng.choice(names), rng.choice(names)) for _ in range(rng.randint(0, 5))]  # loops, back edges
    transitions = []
    for k, (u, v) in enumerate(edges):
        mp = {}
        for tq in states[v]["quantities"]:
            if agreeing:
                mp[tq] = {states[u]["quantities"][0]: str(pot[v] / pot[u])}
            else:
                mp[tq] = {sq: str(Fr(rng.choice([0, 0, 1, -1, 2, 3]), rng.choice([1, 2])))
                          for sq in states[u]["quantities"]}
        transitions.append({"name": f"e{k}", "from": u, "to": v, "map": mp})
    return ra.Model({"initial": names[0], "states": states, "transitions": transitions})


def test_theorem_dim_h0_equals_agreement_dim_on_random_models():
    """dim ker(delta) (from the coboundary matrix) equals the agreement dimension (from routes)
    on 600 random rooted models, including non-invertible maps, zero stalks, self-loops and
    back edges. Both outcomes must occur, so the check is not vacuous."""
    rng = random.Random(20261114)
    agree = disagree = 0
    for i in range(600):
        m = _random_model(rng, agreeing=(i % 3 == 0))
        res = ra.analyse(m)
        assert res["theorem_holds"], (i, res)
        assert res["h0"] == res["agreement_dim"]
        assert res["h1"] == res["h1_by_corollary"], (i, res)
        if res["routes_agree"]:
            agree += 1
        else:
            disagree += 1
    assert agree >= 150 and disagree >= 150, (agree, disagree)


def test_models_built_with_trivial_holonomy_always_agree():
    rng = random.Random(7)
    for _ in range(100):
        assert ra.analyse(_random_model(rng, agreeing=True))["routes_agree"]


# ---------------------------------------------------------------- views and evaluation

def test_views_report_who_can_see_a_disagreement():
    m = _toy("0")
    m.views = {"payer": [], "platform": ["fee"], "payee": ["paid_out"]}
    f = ra.analyse(m)["findings"][0]
    assert f["seen_by"] == ["platform"] and f["not_seen_by"] == ["payee", "payer"]


def test_evaluate_carries_values_along_a_route():
    m = _toy("1/100")
    assert ra.evaluate(m, ["deliver", "settle"], {"amount": 1000}) == {"paid_out": Fr(1000), "fee": Fr(10)}
    assert ra.evaluate(m, ["deliver", "dispute", "uphold"], {"amount": 1000}) == {"paid_out": Fr(1000), "fee": Fr(10)}
    with pytest.raises(ra.ModelError, match="route breaks"):
        ra.evaluate(m, ["settle"], {"amount": 1})


# ---------------------------------------------------------------- scope and input errors

def test_unreachable_state_is_refused():
    with pytest.raises(ra.ModelError, match="not reachable"):
        ra.analyse(ra.Model({"initial": "A", "states": {"A": {"quantities": ["x"]}, "B": {"quantities": ["x"]}},
                             "transitions": [{"name": "loop", "from": "A", "to": "A", "map": {"x": {"x": 1}}}]}))


def test_unknown_quantity_is_refused():
    with pytest.raises(ra.ModelError, match="not a quantity"):
        ra.Model({"states": {"A": {"quantities": ["x"]}, "B": {"quantities": ["y"]}},
                  "transitions": [{"name": "t", "from": "A", "to": "B", "map": {"z": {"x": 1}}}]})


def test_no_single_initial_state_is_refused():
    with pytest.raises(ra.ModelError, match="initial"):
        ra.Model({"states": {"A": {"quantities": ["x"]}, "B": {"quantities": ["x"]}},
                  "transitions": [{"name": "t", "from": "A", "to": "B", "map": {"x": {"x": 1}}},
                                  {"name": "u", "from": "B", "to": "A", "map": {"x": {"x": 1}}}]})
