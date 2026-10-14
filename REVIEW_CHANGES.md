# Review changes (local branch `sage/review-fixes-local`)

**Audience:** Damir's agents reviewing this private branch.  
**Status:** Opened as a pull request for review. Do not merge until Damir and his agents have reviewed and tested it.
**Basis:** findings in `/workspace/notes/sheaf-cohomology-review-2026-10-13.md` (GPT Sol + Sage, 13 Oct 2026).

This note explains every change on the branch, why it was made, how to verify it, the new vs old headline numbers, the safe/unsafe escrow result, and what is still open.

---

## How to verify (exact commands)

From the repo root, with the Python env that has `numpy`, `pyyaml`, and `pytest` (e.g. `/tmp/sheafvenv`):

```bash
# Full regression suite (19 tests)
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

**What:** New `field_loss(...)` (plus `initial_states`) scores invariant fields that are dropped across an edge or missing at a reachable state. Monotone: restoring a missing field can only lower the score. Optional `drops: [...]` on a transition marks an intentional drop (reported, not scored).

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

1. **README and paper figures not updated for current `protocol.yaml`.** README still advertises 1-complex `H¹ = 24`. That remains true for `protocol_paper_v1.yaml` only; current `protocol.yaml` is **28**. Paper prose about "10 faces" / implemented transitions needs a pass against the live YAML.

2. **Toy comment still wrong.** `toy_escrow_protocol.yaml` still says removing `amount` from `carries` "should" produce H¹ = 1. With `carries` now honoured, that edit shrinks C¹ and is caught by `field_loss`, but on a tree **H¹ stays 0**. The comment should point at `field_loss`, not H¹.

3. **Intentional field drops in cancellations need marking.** Paths into `CANCELLED` drop many fields (deadline, service_hash, escrow_*, …) by design. They are not yet annotated with `drops: [...]`, so `field_loss` will score them as real losses once someone runs it on the full ACTP model. Mark declared cancellations before treating the score as a CI gate.

4. **Safety claim still unsupported.** Safe vs unsafe escrow scores are identical (see above). Do not revive "verification and safety" language until a separating example exists.

5. **Other review items left untouched** (by design on this branch): participant-model tautologies, "paths" as induced subgraphs, CI gating only named-path mismatches, archival attestation mutation, README path-interpretation claims (`happy_quoted` H¹=6 explanation).

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
