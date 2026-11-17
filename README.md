# actp-sheaf-cohomology

Reproducibility artifact for the paper:

> **Sheaf Cohomology for Settlement Protocol Verification**
> Justin Rooschüz, Damir Mujić — AGIRAILS Inc., 2026.

This repository contains the runnable supplementary code that reproduces every
quantitative claim made in the paper. All commands in [REPRODUCING.md](REPRODUCING.md)
should produce numbers that match the paper exactly.

## What This Is

A cellular-sheaf model of the [Agent Commerce Transaction Protocol (ACTP)](https://docs.agirails.io)
8-state lifecycle, plus a CLI linter that computes the first cohomology group
**H¹** as a topological-completeness diagnostic for state-machine protocols.

The artifact exposes two related analyses over the same YAML state-machine model:

- **1-complex analysis** — graph-only diagnostics over states and transitions
- **2-complex analysis** — explicit face refinement over parallel protocol paths

It also includes two participant-side supplements:

- `participant_h1.py` — exact six-channel raw-visibility analysis on the higher-order participant complex
- `participant_semantic_h1.py` — conservative semantic four-channel participant model matching the paper's Section 5 table

The 1-complex output is useful as a leak signal. The 2-complex output tests
whether those edge-level mismatches collapse once the relevant higher-order
faces are attached.

## Key Results for the Paper Model `protocol_paper_v1.yaml`

The paper's figures were computed on `protocol_paper_v1.yaml`, which is
byte-identical to the model the paper used (the `protocol.yaml` of the initial
public release). Every command that reproduces a paper figure points at it.

- 1-complex: `H¹ = 24`
- 2-complex: `H¹ = 0`, `H² = 20`, with 10 faces and `C² = 44`
- `δ₁∘δ₀ = 0` numerically, with residual `0.0e+00`

For the paper's reduced ACTP basis this means:

- the graph abstraction exposes 24 edge-level obstructions
- the explicit 2-cell refinement closes them
- ACTP is topologically complete on the published 2-complex model

## `protocol.yaml` Is the Current-Kernel Model

`protocol.yaml` (the linter's default) models the current kernel. It adds the
`DISPUTED → CANCELLED` transition (`cancel_disputed`) and the face
`cancel_via_dispute`, so its numbers differ from the paper's:

- 1-complex: `H¹ = 28` (`C¹ = 76`)
- 2-complex: `H¹ = 0`, `H² = 20`, with 11 faces and `C² = 48`

Use it for current analysis; use `protocol_paper_v1.yaml` to reproduce the paper.

## Quick Start

```bash
pip install -r requirements.txt   # numpy, pyyaml

# Main paper claim — Theorem 3.6: H¹ = 0 on the 2-complex (24 / 0 / 20, 10 faces)
python3 h1_lint.py --config protocol_paper_v1.yaml --2complex

# 1-complex diagnostic with subgraph breakdown (Table 2)
python3 h1_lint.py --config protocol_paper_v1.yaml

# Current-kernel model (28 / 0 / 20, 11 faces)
python3 h1_lint.py --config protocol.yaml --2complex

# Rational arithmetic cross-validation (Section 3.2)
python3 verify_rational.py
```

For the full reproduction recipe, see [REPRODUCING.md](REPRODUCING.md).

## Files

| File | Paper reference | Purpose |
|---|---|---|
| `protocol_paper_v1.yaml` | Tables 1–3, Theorem 3.6 | The paper's ACTP v2.7 model with 10 faces (reproduces 24 / 0 / 20) |
| `protocol.yaml` | — (current kernel) | Current-kernel model: adds `DISPUTED → CANCELLED` and face `cancel_via_dispute`; 11 faces, 28 / 0 / 20 |
| `h1_engine.py` | Section 6.2 | Core sheaf computation engine |
| `h1_lint.py` | Section 6.3 | CI-ready linter (`--2complex`, `--diff`, `--leaks`, `--json`) |
| `participant_semantic_h1.py` | Table 4, Appendix D | Conservative 4-channel participant model |
| `participant_h1.py` | Appendix E | Exact 6-channel raw-visibility model |
| `verify_rational.py` | Section 3.2 | Exact rational arithmetic cross-validation |
| `actp_sheaf.py` | Section 6 | Original archival reference implementation |
| `toy_escrow_protocol.yaml` | Section 8 | 3-state toy (methodology validation, expected H¹ = 0) |
| `toy_escrow_broken.yaml` | Section 8 | 4-state broken toy (gap detection test, expected H¹ = 4) |
| `H1_LINTER_SPEC.md` | — | Linter contract and YAML schema notes |

## YAML Model

The public interface is the YAML model (`protocol.yaml` by default).

- `states` define vertex stalks
- `transitions` define directed edges; optional `carries: [...]` sets the edge
  stalk, optional `drops: [...]` declares an intentional field drop
- `initial` (optional) names the initial state or states; without it, the
  initial states are those with no incoming edge other than self-loops
- `paths` define named subgraphs for targeted diagnostics
- `faces` define explicit 2-cells as the formal difference of two directed paths with identical endpoints

Example:

```yaml
faces:
  - name: quote_commit
    plus: [submitQuote, linkEscrow_quoted]
    minus: [linkEscrow_direct]
```

The face stalk is computed automatically as the intersection of all edge stalks
appearing in the boundary.

## Field Loss

H¹ counts cycles in each field's support graph, not lost data. The linter also
prints a direct `field_loss` score: the number of (state, field) pairs where a
field is expected (reachable from an initial state that holds it, along a path
with no declared `drops` of it) but absent from the state's stalk. The default
output is one summary line; `--field-loss` lists each pair with a witness path,
and `--track-introduced` also tracks fields introduced after the initial state.
A finding is a model-level statement about the YAML stalks, not about contract
storage: the stalk labels are an abstraction, and the real kernel keeps one
struct per transaction. In the default mode, adding a field to a non-initial
state's stalk never raises the score; enlarging an initial state's stalk, or
`--track-introduced`, carries no such guarantee.

## Current Interpretation

- `happy` path: `H¹ = 0`
- `happy_quoted`: `H¹ = 6` on the 1-complex because quote-specific data is not carried into `COMMITTED`
- `dispute`: `H¹ = 6` on the 1-complex
- `cancellation`: `H¹ = 18` on the 1-complex because terminal cancellations discard many fields
- full 2-complex: `H¹ = 0`

For the higher-order participant supplement:

- graph-only six-channel raw-visibility counts are large (21 to 48) because the participant `K4` leaves public cycles unfilled
- once the four public-information faces are added, the exact six-channel raw-visibility model yields `H¹ = 0` at every ACTP state
- this shows that the paper's participant table is a conservative semantic upper bound, not an exact raw-visibility invariant

For the conservative semantic participant supplement:

- `participant_semantic_h1.py` reproduces the Section 5 upper-bound table exactly
- the per-state values are `6, 7, 7, 7, 8, 7, 8, 6`
- this turns the paper's semantic participant theorem into a runnable artifact rather than a hand-maintained table

## Citation

If you use this artifact, please cite the paper:

```bibtex
@misc{rooschuz2026sheaf,
  title  = {Sheaf Cohomology for Settlement Protocol Verification},
  author = {Roosch\"{u}z, Justin and Muji\'{c}, Damir},
  year   = {2026},
  note   = {AGIRAILS Inc.}
}
```

A machine-readable [CITATION.cff](CITATION.cff) is also provided.

## License

Apache-2.0. See [LICENSE](LICENSE).
