"""Regression tests for the review findings (Oct 2026)."""
import copy
import os
import subprocess
import sys

import pytest
import yaml

from h1_engine import (
    analyse_protocol, analyse_protocol_2complex, field_loss,
    validate_protocol, ProtocolValidationError,
)
import verify_rational

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures")


def load(path):
    with open(os.path.join(ROOT, path)) as f:
        p = yaml.safe_load(f)
    states = {k: (v["stalks"] if isinstance(v, dict) else v) for k, v in p["states"].items()}
    return states, p["transitions"], p.get("faces", [])


# --- reproduction ---------------------------------------------------------

def test_paper_v1_numbers_reproduce():
    s, t, f = load("protocol_paper_v1.yaml")
    assert analyse_protocol(s, t)["dim_h1"] == 24
    two = analyse_protocol_2complex(s, t, f)
    assert (two["dim_h1"], two["dim_h2"], two["rank_delta0"], two["rank_delta1"]) == (0, 20, 48, 24)


def test_current_model_with_disputed_cancelled():
    s, t, f = load("protocol.yaml")
    assert any(x["from"] == "DISPUTED" and x["to"] == "CANCELLED" for x in t)
    two = analyse_protocol_2complex(s, t, f)
    assert two["dim_h1"] == 0  # the added face keeps the 2-complex result
    assert two["complex_residual"] == 0


# --- field-loss score (direct, not cycle counting) -------------------------

def test_restoring_missing_field_lowers_field_loss():
    s, t, _ = load("toy_escrow_broken.yaml")
    before = field_loss(s, t)
    assert [(m["state"], m["field"]) for m in before["missing"]] == [("DISPUTE", "amount")]
    s2 = copy.deepcopy(s)
    s2["DISPUTE"].append("amount")
    after = field_loss(s2, t)
    assert after["score"] < before["score"]
    assert after["score"] == 0
    # Documented contrast: H^1 moves the *wrong* way on the same edit.
    assert analyse_protocol(s2, t)["dim_h1"] > analyse_protocol(s, t)["dim_h1"]


def test_tree_that_drops_field_is_flagged():
    s = {"A": ["id", "amount"], "B": ["id"]}
    t = [{"from": "A", "to": "B", "name": "step"}]
    assert analyse_protocol(s, t)["dim_h1"] == 0  # H^1 cannot see it
    fl = field_loss(s, t)
    assert fl["score"] == 1  # one (state, field) pair: amount expected at B
    assert fl["dropped"][0]["field"] == "amount"  # per-edge detail, unscored


def test_declared_drop_is_not_scored():
    s = {"A": ["id", "amount"], "B": ["id"]}
    t = [{"from": "A", "to": "B", "name": "step", "drops": ["amount"]}]
    fl = field_loss(s, t)
    assert fl["score"] == 0 and len(fl["declared_drops"]) == 1


def test_toy_happy_escrow_has_no_field_loss():
    s, t, _ = load("toy_escrow_protocol.yaml")
    assert field_loss(s, t)["score"] == 0


# --- carries is honoured ---------------------------------------------------

def test_carries_is_honoured():
    s, t, _ = load("toy_escrow_protocol.yaml")
    t2 = copy.deepcopy(t)
    t2[1]["carries"].remove("amount")
    base = analyse_protocol(s, t)
    cut = analyse_protocol(s, t2)
    assert cut["dim_c1"] == base["dim_c1"] - 1
    fl = field_loss(s, t2)
    assert {"transition": "release", "from": "DELIVER", "to": "RELEASE", "field": "amount"} in fl["dropped"]


def test_carries_must_be_shared():
    s = {"A": ["x"], "B": ["y"]}
    with pytest.raises(ProtocolValidationError):
        validate_protocol(s, [{"from": "A", "to": "B", "name": "e", "carries": ["x"]}])


# --- input validation ------------------------------------------------------

def test_duplicate_field_label_rejected():
    with pytest.raises(ProtocolValidationError, match="duplicate field"):
        analyse_protocol({"A": ["x", "x"], "B": ["x"]}, [{"from": "A", "to": "B", "name": "e"}])


def test_duplicate_transition_and_face_names_rejected():
    s = {"A": ["x"], "B": ["x"]}
    with pytest.raises(ProtocolValidationError):
        validate_protocol(s, [{"from": "A", "to": "B", "name": "e"}, {"from": "B", "to": "A", "name": "e"}])
    t = [{"from": "A", "to": "B", "name": "e1"}, {"from": "A", "to": "B", "name": "e2"}]
    f = [{"name": "f", "plus": ["e1"], "minus": ["e2"]}, {"name": "f", "plus": ["e2"], "minus": ["e1"]}]
    with pytest.raises(ProtocolValidationError, match="duplicate face"):
        analyse_protocol_2complex(s, t, f)


def test_unknown_state_rejected():
    with pytest.raises(ProtocolValidationError):
        analyse_protocol({"A": ["x"]}, [{"from": "A", "to": "Z", "name": "e"}])


def test_invalid_face_raises_instead_of_negative_score():
    # Face whose two sides do not share endpoints: delta1.delta0 != 0,
    # which previously produced negative "dimensions" such as H^1 = -1.
    s = {"A": ["x"], "B": ["x"], "C": ["x"]}
    t = [{"from": "A", "to": "B", "name": "ab"}, {"from": "B", "to": "C", "name": "bc"}]
    f = [{"name": "bad", "plus": ["ab"], "minus": ["bc"]}]
    with pytest.raises(ProtocolValidationError, match="not form a valid 2-complex"):
        analyse_protocol_2complex(s, t, f)


@pytest.mark.parametrize("path", ["protocol.yaml", "protocol_paper_v1.yaml",
                                  "toy_escrow_protocol.yaml", "toy_escrow_broken.yaml"])
def test_no_negative_dimensions(path):
    s, t, f = load(path)
    r = analyse_protocol(s, t)
    assert min(v for k, v in r.items() if k.startswith("dim_")) >= 0
    if f:
        r2 = analyse_protocol_2complex(s, t, f)
        assert min(v for k, v in r2.items() if k.startswith("dim_")) >= 0


# --- verify_rational -------------------------------------------------------

def test_rational_builder_handles_self_loop():
    s = {"A": ["x"]}
    t = [{"from": "A", "to": "A", "name": "loop"}]
    d0, n_v, n_e = verify_rational.build_delta0_rational(s, t)
    assert d0 == [[0]]
    assert n_e - verify_rational.rational_rank(d0) == analyse_protocol(s, t)["dim_h1"] == 1


def test_verify_rational_cli_exit_codes(tmp_path):
    ok = subprocess.run([sys.executable, "verify_rational.py"], cwd=ROOT, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    # Force a mismatch by making the production engine disagree, and check exit code 1.
    forced = subprocess.run(
        [sys.executable, "-c",
         "import sys, runpy, h1_engine\n"
         "orig = h1_engine.analyse_protocol\n"
         "def bad(*a, **k):\n"
         "    r = orig(*a, **k); r['dim_h1'] += 1; return r\n"
         "h1_engine.analyse_protocol = bad\n"
         "runpy.run_path('verify_rational.py', run_name='__main__')\n"],
        cwd=ROOT, capture_output=True, text=True)
    assert forced.returncode == 1, forced.stdout + forced.stderr
    assert "MISMATCH" in forced.stdout


# --- safe vs unsafe escrow discrimination ----------------------------------

def test_safe_vs_unsafe_escrow_not_discriminated():
    """Documents the core limitation: the two escrows differ only in WHO may
    release funds, and every score the tool produces is identical. Until this
    test can be flipped to assert a difference, the tool must not be described
    as a safety verifier."""
    s1, t1, _ = load("tests/fixtures/escrow_safe.yaml")
    s2, t2, _ = load("tests/fixtures/escrow_unsafe.yaml")
    assert [x["actor"] for x in t1] != [x["actor"] for x in t2]  # they really differ
    assert analyse_protocol(s1, t1) == analyse_protocol(s2, t2)
    assert field_loss(s1, t1) == field_loss(s2, t2)


# --- field-loss path-closure semantics (second pass, 2026-11-14) -----------

def _fan_out(restore_at_b=False):
    """A(id,amt) -> B(id) -> {C1,C2,C3}(id), optionally with amt restored at B."""
    s = {"A": ["id", "amt"], "B": ["id", "amt"] if restore_at_b else ["id"],
         "C1": ["id"], "C2": ["id"], "C3": ["id"]}
    t = [{"from": "A", "to": "B", "name": "ab"}]
    t += [{"from": "B", "to": c, "name": "b_" + c} for c in ("C1", "C2", "C3")]
    return s, t


def test_field_loss_is_monotone_on_fan_out():
    s, t = _fan_out()
    before = field_loss(s, t)
    assert before["score"] == 4  # amt expected at B, C1, C2, C3
    after = field_loss(*_fan_out(restore_at_b=True))
    assert after["score"] == 3   # restoring at B removes exactly one pair
    assert after["score"] < before["score"]


def test_field_loss_restore_at_dispute_never_worse():
    s, t, _ = load("toy_escrow_broken.yaml")
    before = field_loss(s, t)
    s2 = copy.deepcopy(s)
    s2["DISPUTE"].append("amount")
    assert field_loss(s2, t)["score"] <= before["score"]


def test_restoring_any_missing_pair_lowers_score_by_one():
    s, t, _ = load("protocol.yaml")
    base = field_loss(s, t)
    for pair in base["missing"]:
        s2 = copy.deepcopy(s)
        s2[pair["state"]].append(pair["field"])
        assert field_loss(s2, t)["score"] == base["score"] - 1, pair


def test_declared_non_terminal_drop_excuses_downstream():
    s = {"A": ["id", "amt"], "B": ["id"], "C": ["id"], "D": ["id"]}
    t = [{"from": "A", "to": "B", "name": "ab", "drops": ["amt"]},
         {"from": "B", "to": "C", "name": "bc"},
         {"from": "C", "to": "D", "name": "cd"}]
    fl = field_loss(s, t)
    assert fl["score"] == 0 and fl["missing"] == []


def test_mixed_declared_and_undeclared_paths_still_flag():
    # A -> B declares the drop, but A -> M -> B does not: amt is still expected at B.
    s = {"A": ["id", "amt"], "M": ["id", "amt"], "B": ["id"]}
    t = [{"from": "A", "to": "B", "name": "direct", "drops": ["amt"]},
         {"from": "A", "to": "M", "name": "am"},
         {"from": "M", "to": "B", "name": "mb"}]
    fl = field_loss(s, t)
    assert [(m["state"], m["field"]) for m in fl["missing"]] == [("B", "amt")]
    assert fl["missing"][0]["path"] == ["A", "M", "B"]
    assert fl["missing"][0]["via"] == ["am", "mb"]
    assert fl["score"] == 1


def test_field_loss_witness_path_for_fan_out():
    s, t = _fan_out()
    by_state = {m["state"]: m for m in field_loss(s, t)["missing"]}
    assert by_state["C2"]["path"] == ["A", "B", "C2"]
    assert by_state["C2"]["via"] == ["ab", "b_C2"]


def test_track_introduced_fields_mode():
    # x is introduced at B (not at the initial state) and lost at C.
    s = {"A": ["id"], "B": ["id", "x"], "C": ["id"]}
    t = [{"from": "A", "to": "B", "name": "ab"}, {"from": "B", "to": "C", "name": "bc"}]
    assert field_loss(s, t)["score"] == 0
    fl = field_loss(s, t, origins="all")
    assert [(m["state"], m["field"]) for m in fl["missing"]] == [("C", "x")]
    # Not monotone in this mode: introducing x at a non-initial state adds obligations.
    s0 = {"A": ["id"], "B": ["id"], "C": ["id"]}
    assert field_loss(s0, t, origins="all")["score"] == 0 < fl["score"]


# --- initial states: no silent zero ----------------------------------------

def _retry_model():
    s = {"START": ["id", "amt"], "WORK": ["id"]}
    t = [{"from": "START", "to": "WORK", "name": "go"},
         {"from": "WORK", "to": "START", "name": "retry"}]
    return s, t


def test_no_initial_state_raises():
    s, t = _retry_model()
    with pytest.raises(ValueError, match="no initial state"):
        field_loss(s, t)


def test_explicit_initial_key_works():
    s, t = _retry_model()
    fl = field_loss(s, t, initial="START")
    assert fl["initial_states"] == ["START"]
    assert [(m["state"], m["field"]) for m in fl["missing"]] == [("WORK", "amt")]


def test_self_loop_on_start_keeps_it_initial():
    s = {"START": ["id", "amt"], "WORK": ["id"]}
    t = [{"from": "START", "to": "START", "name": "poll"},
         {"from": "START", "to": "WORK", "name": "go"}]
    fl = field_loss(s, t)
    assert fl["initial_states"] == ["START"]
    assert fl["score"] == 1


def test_unknown_initial_state_rejected():
    s, t = _retry_model()
    with pytest.raises(ProtocolValidationError):
        field_loss(s, t, initial="NOPE")


# --- linter output and plumbing --------------------------------------------

def _lint(*args):
    return subprocess.run([sys.executable, "h1_lint.py", *args], cwd=ROOT,
                          capture_output=True, text=True)


def test_lint_default_prints_one_field_loss_line():
    r = _lint("--config", "protocol.yaml")
    assert r.returncode == 0, r.stderr
    lines = [l for l in r.stdout.splitlines() if "FIELD LOSS" in l or l.strip().startswith("missing ")]
    assert len(lines) == 1, lines
    assert "--field-loss" in lines[0]


def test_lint_field_loss_flag_prints_pairs_with_witness():
    r = _lint("--config", "protocol.yaml", "--field-loss")
    assert r.returncode == 0, r.stderr
    assert "missing  deadline" in r.stdout and "INITIATED --cancel_initiated--> CANCELLED" in r.stdout
    assert "not about contract storage" in r.stdout


def _write_yaml(tmp_path, doc):
    path = tmp_path / "m.yaml"
    path.write_text(yaml.safe_dump(doc))
    return str(path)


RETRY_DOC = {
    "states": {"START": {"stalks": ["id", "amt"]}, "WORK": {"stalks": ["id"]}},
    "transitions": [{"from": "START", "to": "WORK", "name": "go"},
                    {"from": "WORK", "to": "START", "name": "retry"}],
}


def test_lint_reads_initial_key(tmp_path):
    bad = _lint("--config", _write_yaml(tmp_path, RETRY_DOC), "--field-loss")
    assert bad.returncode != 0 and "no initial state" in (bad.stdout + bad.stderr)
    good = _lint("--config", _write_yaml(tmp_path, dict(RETRY_DOC, initial="START")), "--field-loss")
    assert good.returncode == 0, good.stderr
    assert "missing  amt" in good.stdout


def test_lint_track_introduced_flag(tmp_path):
    doc = {"states": {"A": {"stalks": ["id"]}, "B": {"stalks": ["id", "x"]}, "C": {"stalks": ["id"]}},
           "transitions": [{"from": "A", "to": "B", "name": "ab"}, {"from": "B", "to": "C", "name": "bc"}]}
    path = _write_yaml(tmp_path, doc)
    assert "missing  x" not in _lint("--config", path, "--field-loss").stdout
    assert "missing  x" in _lint("--config", path, "--field-loss", "--track-introduced").stdout
