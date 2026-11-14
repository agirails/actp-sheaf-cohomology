# Review changes (local branch `sage/review-fixes-local`)

**Audience:** Damir's agents reviewing this private branch.  
**Status:** Opened as a pull request for review. Do not merge until Damir and his agents have reviewed and tested it.
**Basis:** findings in `/workspace/notes/sheaf-cohomology-review-2026-10-13.md` (GPT Sol + Sage, 13 Oct 2026).

This note explains every change on the branch, why it was made, how to verify it, the new vs old headline numbers, the safe/unsafe escrow result, and what is still open.

---

## How to verify (exact commands)

From the repo root, with the Python env that has `numpy`, `pyyaml`, and `pytest` (e.g. `/tmp/sheafvenv`):

```bash
# Full regression suite (39 tests after the second pass)
/tmp/sheafvenv/bin/python -m pytest tests/ -q

# Paper-scoped model still reproduces README Theorem 3.6 numbers
/tmp/sheafvenv/bin/python -c "
import yaml
from h1_engine import analyse_protocol, analyse_protocol_2complex
p=yaml.safe_load(open('protocol_paper_v1.yaml'))
s={k:v['stalks'] for k,v in p['states'].items()}
g=analyse_protocol(s,p['transitions'])
two=analyse_protocol_2complex(s,p['transitions'],p['faces'])
print('paper_v1 graph H1', g['dim_h1'], '2c H1/H2', two['dim_h1'], two['dim_h2'])
"

# Current protocol.yaml (with DISPUTED→CANCELLED)
/tmp/sheafvenv/bin/python -c "
import yaml
from h1_engine import analyse_protocol, analyse_protocol_2complex
p=yaml.safe_load(open('protocol.yaml'))
s={k:v['stalks'] for k,v in p['states'].items()}
g=analyse_protocol(s,p['transitions'])
two=analyse_protocol_2complex(s,p['transitions'],p['faces'])
print('current graph H1', g['dim_h1'], '2c H1/H2', two['dim_h1'], two['dim_h2'])
"

# Rational cross-check (exit 0 on agree, 1 on mismatch)
/tmp/sheafvenv/bin/python verify_rational.py

# Human lint of current model (shows H¹ note + field-loss block)
/tmp/sheafvenv/bin/python h1_lint.py --config protocol.yaml --2complex
```

---

## New vs old figures

| Model | Graph H¹ | 2-complex H¹ | H² | Notes |
|---|---:|---:|---:|---|
| `protocol_paper_v1.yaml` (snapshot of pre-fix YAML) | **24** | **0** | **20** | Reproduces README / Theorem 3.6 / review §1 table |
| `protocol.yaml` (current, + `DISPUTED→CANCELLED` + face `cancel_via_dispute`) | **28** | **0** | **20** | Graph H¹ rises by 4; the new face keeps 2-complex H¹ at 0 |

So: paper numbers are preserved in `protocol_paper_v1.yaml`. The live `protocol.yaml` is intentionally a richer model and no longer matches the paper's "H¹ = 24" line for the 1-complex.

---

## Safe vs unsafe escrow (tool cannot judge safety)

Fixtures: `tests/fixtures/escrow_safe.yaml` and `tests/fixtures/escrow_unsafe.yaml`.

They differ only in `actor` on the `release` transition (payer vs payee). The sheaf model never reads `actor`.

Result (asserted by `test_safe_vs_unsafe_escrow_not_discriminated`):

- `analyse_protocol` scores are **identical** (H¹ = 0, same dimensions).
- `field_loss` scores are **identical** (score = 0).

**Conclusion for reviewers:** until a score separates an independently confirmed safe/unsafe pair, this tool must not be described as a safety or authorization verifier. That matches the review verdict (notes §2 "Does H¹ establish safety…" and §5 "Single best next step").

---

## Change-by-change

### 1. `field_loss` score — `h1_engine.py`

**Why:** Review §2 showed H¹ counts cycles in each field's support graph, not dropped data. Restoring missing `amount` at DISPUTE in `toy_escrow_broken.yaml` *raises* H¹ (4→5); a single tree edge that drops a field has H¹ = 0.

**What:** New `field_loss(...)` (plus `initial_states`) scores invariant fields that are dropped across an edge or missing at a reachable state. Optional `drops: [...]` on a transition marks an intentional drop (reported, not scored).

**Superseded (second pass):** the first-pass claim that this score was monotone was false (restoring `amt` at B in A(id,amt)→B(id)→{C1,C2,C3} moved it 5→6). The score was redefined; see "Second pass (2026-11-14)" below.

**Verify:** `pytest` tests `test_restoring_missing_field_lowers_field_loss`, `test_tree_that_drops_field_is_flagged`, `test_declared_drop_is_not_scored`.

### 2. Honour `carries` — `h1_engine.py` / `verify_rational.py`

**Why:** Review §3: edge stalks ignored `carries`; the toy's advertised gap test was a no-op.

**What:** `_edge_fields` uses a transition's `carries` list when present (must be ⊆ both endpoints); otherwise falls back to shared endpoint fields. Rational builder uses the same rule.

**Verify:** `test_carries_is_honoured`, `test_carries_must_be_shared`.

### 3. Input validation — `h1_engine.py` / `h1_lint.py`

**Why:** Review §3: duplicate field labels, duplicate face names, and invalid faces produced wrong or negative "dimensions".

**What:** `validate_protocol` + `ProtocolValidationError`. Rejects duplicate state fields, duplicate transition/face names, unknown states/edges, bad `carries`/`drops`. `compute_h1_2complex` raises if `δ₁δ₀ ≠ 0` instead of returning negative dims. CLI `load_protocol` runs the same checks.

**Verify:** `test_duplicate_field_label_rejected`, `test_duplicate_transition_and_face_names_rejected`, `test_invalid_face_raises_instead_of_negative_score`, `test_no_negative_dimensions`.

### 4. `verify_rational.py` self-loops and exit code

**Why:** Review §3: self-loop overwrote +1 with −1 (should accumulate to 0); mismatches printed ❌ but exited 0.

**What:** Accumulate ±1 on self-loops; also compare against production `analyse_protocol`; `sys.exit(1)` on mismatch.

**Verify:** `test_rational_builder_handles_self_loop`, `test_verify_rational_cli_exit_codes`.

### 5. `DISPUTED → CANCELLED` — `protocol.yaml` + `protocol_paper_v1.yaml`

**Why:** Review §3: paper describes the transition as implemented; reduced YAML omitted it.

**What:** Added `cancel_disputed` and face `cancel_via_dispute` to `protocol.yaml`. Frozen the pre-fix YAML as `protocol_paper_v1.yaml` so paper numbers stay reproducible.

**Verify:** `test_paper_v1_numbers_reproduce`, `test_current_model_with_disputed_cancelled`; figures table above.

### 6. False paper remark — `sheaf_cohomology_actp_pub.tex`

**Why:** Review §2: "any subspace of this maximal stalk still fills the same 1-cycles" is false; zero face stalks return H¹ to 24.

**What:** Remark rewritten to say shrinking face stalks can raise H¹.

**Verify:** Diff around the remark near former line ~719; numerical extreme case is the graph H¹ of the same model.

### 7. Linter messaging — `h1_lint.py`

**Why:** Make the cycle-vs-loss distinction visible in the default CLI output.

**What:** Prints a one-line note that H¹ counts support-graph cycles, then a FIELD LOSS block from `field_loss`.

### 8. Test suite — `tests/`

**Why:** Review §3: no automated tests; recommended field-loss counterexamples, duplicate rejection, self-loops, safe/unsafe pair.

**What:** 19 pytest cases covering reproduction, field-loss, carries, validation, rational builder, and the non-discrimination of safe vs unsafe escrow.

---

## Known open items (not fixed on this branch)

1. **README figures (resolved in the second pass).** Paper-figure commands now point at `protocol_paper_v1.yaml`; `protocol.yaml` is documented as the current-kernel model. The paper's own prose ("10 faces", Theorem 3.6) is unchanged by design: it describes the paper model.

2. **Toy comment (resolved in the second pass).** See second pass, item 7.

3. **Intentional field drops in cancellations need marking.** Paths into `CANCELLED` drop `deadline` and `service_hash` by design, and `SETTLED` lacks `deadline`. They are not annotated with `drops: [...]`, so `field_loss` scores 3 on `protocol.yaml` (and on `protocol_paper_v1.yaml`). Mark declared drops before treating the score as a CI gate.

4. **Safety claim still unsupported.** Safe vs unsafe escrow scores are identical (see above). Do not revive "verification and safety" language until a separating example exists.

5. **Other review items left untouched** (by design on this branch): participant-model tautologies, "paths" as induced subgraphs, CI gating only named-path mismatches, archival attestation mutation, README path-interpretation claims (`happy_quoted` H¹=6 explanation).

---

## Second pass (2026-11-14)

Branch `apex/review-fixes-2`, on top of `sage/review-fixes`. Fixes from an independent review of the first pass. Each fix has a test that was red before it.

### 1. `field_loss` redefined by path closure (blocker: not monotone) — `h1_engine.py`

The per-edge score was not monotone: in A(id,amt)→B(id)→{C1,C2,C3}(id), restoring `amt` at B made every edge out of B count as a drop (5→6). `field_loss` now counts **(state, field) pairs**:

- **Initial states:** the top-level YAML `initial:` key (a name or list) if present, else the states with no incoming edge other than self-loops.
- **Expected:** f is expected at s if some path from an initial state holding f reaches s with no transition declaring `drops: [f]`. A declared drop excuses everything downstream on that path; a state also reached by an undeclared path is still expected to have f.
- **Score:** pairs with f expected at s and f absent from s's stalk; each pair carries one shortest witness path (`path`, `via`).
- **Monotone in the default mode:** the expected set depends only on the graph, the declared drops and the initial states' stalks, so adding a field to a non-initial state's stalk can only remove pairs. Enlarging an initial state's stalk adds obligations and can raise the score.
- **`origins="all"`** (CLI `--track-introduced`): a field introduced at any reachable state is tracked downstream of it. Not monotone, as documented.
- The old per-edge listing remains as `dropped` (unscored detail).

Tests: `test_field_loss_is_monotone_on_fan_out` (4→3), `test_field_loss_restore_at_dispute_never_worse`, `test_restoring_any_missing_pair_lowers_score_by_one`, `test_declared_non_terminal_drop_excuses_downstream`, `test_mixed_declared_and_undeclared_paths_still_flag`, `test_field_loss_witness_path_for_fan_out`, `test_track_introduced_fields_mode`. Two first-pass tests were updated to the pair semantics (`test_restoring_missing_field_lowers_field_loss`, `test_tree_that_drops_field_is_flagged`: score 1, not 2).

### 2. No silent zero (blocker) — `h1_engine.py`, `h1_lint.py`

If no initial state can be found (every state has a non-self-loop incoming edge), `initial_states` raises `ProtocolValidationError` (a `ValueError`) asking for an `initial:` key. A self-loop on the start state no longer hides it. The linter reads `initial:` and reports the error instead of a score (exit 1 under `--field-loss`).

Tests: `test_no_initial_state_raises`, `test_explicit_initial_key_works`, `test_self_loop_on_start_keeps_it_initial`, `test_unknown_initial_state_rejected`, `test_lint_reads_initial_key`.

### 3. Paper figures point at `protocol_paper_v1.yaml` (blocker) — `README.md`, `REPRODUCING.md`, `H1_LINTER_SPEC.md`

Every command reproducing a paper figure (24 / 0 / 20, 10 faces, C² = 44) now uses `protocol_paper_v1.yaml`, which `cmp` confirms is byte-identical to `protocol.yaml` at `2ded063` and `f18490e`. New sections describe `protocol.yaml` as the current-kernel model (adds `DISPUTED→CANCELLED`, face `cancel_via_dispute`): 28 / 0 / 20, 11 faces, C² = 48. No number in the `.tex` changed.

### 4. Face-stalk remark wording — `sheaf_cohomology_actp_pub.tex`

Same mathematics, tighter statements: shrinking a face stalk to a subspace replaces δ₁ by Pδ₁ for the projection P (removing rows only for a coordinate subspace); it "cannot shrink ker δ₁"; the H¹ = 0 result "is not guaranteed for other choices". The PDF was not rebuilt.

### 5. Linter output — `h1_lint.py`, `README.md`

The default output prints one field-loss line (`FIELD LOSS  score = 3  (model-level; run with --field-loss for details)`). `--field-loss` prints each pair with its witness path, the unscored per-edge detail, and the sentence that a finding is a model-level statement about the YAML stalks, not about contract storage. Tests: `test_lint_default_prints_one_field_loss_line`, `test_lint_field_loss_flag_prints_pairs_with_witness`, `test_lint_track_introduced_flag`.

### 6. Test gaps — `tests/test_engine.py`, `verify_rational.py`

- (a) Reverting the `carries` handling in `verify_rational.py` now turns `test_rational_builder_honours_carries` and `test_verify_rational_checks_dimensions_with_partial_carries` red (checked by reverting, running, restoring). `verify_protocol` now compares C⁰, C¹ and rank(δ₀) with the engine, not only H¹, which a tree cannot distinguish.
- (b) `test_current_model_with_disputed_cancelled` pins graph H¹ = 28, 2-complex H¹ = 0, H² = 20, faces = 11.
- (c) `verify_rational.py` rebuilds δ₁ in exact arithmetic, checks δ₁δ₀ = 0 exactly, and verifies 2-complex H¹ and H² from exact ranks against numpy and the engine, for both `protocol_paper_v1.yaml` and `protocol.yaml`; it exits 1 on mismatch. Tests: `test_rational_delta1_rank_and_2complex`, `test_verify_rational_cli_catches_2complex_mismatch`.

### 7. Nits

- `toy_escrow_protocol.yaml` header: removing `amount` from the `release` carries list leaves H¹ at 0 (tree), shrinks C¹ 10→9 and raises H⁰ 7→8; `field_loss` stays 0 because RELEASE still holds `amount` (the edge appears in the unscored `dropped` detail). Pinned in `test_carries_is_honoured`.
- This section.

### Verification commands (second pass)

```bash
.venv/bin/python -m pytest tests/ -q                                  # 39 passed
.venv/bin/python verify_rational.py; echo EXIT=$?                     # ALL CROSS-VALIDATIONS PASSED, EXIT=0
.venv/bin/python h1_lint.py --config protocol_paper_v1.yaml --2complex   # 1-complex H¹ 24; 2-complex H¹ 0, H² 20, 10 faces
.venv/bin/python h1_lint.py --config protocol.yaml --2complex            # 1-complex H¹ 28; 2-complex H¹ 0, H² 20, 11 faces
.venv/bin/python h1_lint.py --config protocol.yaml --2complex --field-loss   # 3 pairs with witness paths
```

---

## File list on this branch

| Path | Role |
|---|---|
| `h1_engine.py` | validation, `carries`, `field_loss`, complex residual guard |
| `h1_lint.py` | validate on load; print field-loss + H¹ note |
| `verify_rational.py` | `carries`, self-loops, engine cross-check, exit 1 |
| `protocol.yaml` | + `cancel_disputed` + face |
| `protocol_paper_v1.yaml` | frozen pre-fix model (24/0/20) |
| `sheaf_cohomology_actp_pub.tex` | corrected face-stalk remark |
| `tests/` | regression suite + escrow fixtures |
| `.gitignore` | pytest/cache noise |
| `REVIEW_CHANGES.md` | this file |

New helpers in `h1_engine.py` (`ProtocolValidationError`, `_edge_fields`, `validate_protocol`, `initial_states`, `field_loss`) already carry short docstrings. No new undocumented functions were added in `h1_lint.py` or `verify_rational.py`.

## Third pass (2026-11-14): route agreement and README

Added, not changing any existing computation:
- `route_agreement.py`, `ROUTE_AGREEMENT.md`, `models/toy_fee_routes*.yaml`, `tests/test_route_agreement.py` (14 tests): a second sheaf construction whose maps carry the accounting, with a proved theorem (H⁰ is the agreement subspace of routes) and a 600-model random check that computes dim H⁰ two independent ways.
- `README.md` rewritten around the two tools, with a table of what each output does and does not measure and a Status section on the paper.
- `docs/README-VISUALS.md`: a brief for the README's animated diagram.

Verification:

```bash
python -m pytest tests/ -q                                          # 53 passed
python route_agreement.py --config models/toy_fee_routes.yaml       # exit 0, ROUTES AGREE
python route_agreement.py --config models/toy_fee_routes_leaky.yaml # exit 1, names the two routes and the fee
python h1_lint.py --config protocol_paper_v1.yaml --2complex        # unchanged: 24 / 0 / 20
```
