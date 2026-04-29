# H¹ / H² Linter Specification

## Purpose

Turn the ACTP sheaf analysis into an engineering artifact that can be rerun on
edited protocol YAML.

The public CLI supports:

- graph-based `1-complex` diagnostics
- explicit `2-complex` diagnostics when `faces:` are present
- named-path checks
- diff mode
- JSON output
- dimension leak tracing

## Usage

```bash
# Default: analyse the bundled ACTP state machine
python3 h1_lint.py

# Include explicit 2-complex computation
python3 h1_lint.py --2complex

# Custom state machine
python3 h1_lint.py --config protocol.yaml

# Compare two configs
python3 h1_lint.py --diff v1.yaml v2.yaml

# Machine-readable output
python3 h1_lint.py --config protocol.yaml --json --2complex
```

## YAML Schema

```yaml
name: "ACTP"
version: "2.7.0"

states:
  INITIATED:
    stalks: [transaction_id, requester_address, provider_address, amount, deadline, service_hash]

transitions:
  - from: INITIATED
    to: QUOTED
    name: submitQuote

paths:
  happy:
    states: [INITIATED, COMMITTED, IN_PROGRESS, DELIVERED, SETTLED]
    description: "Normal transaction flow"
    expect_h1: 0

faces:
  - name: quote_commit
    plus: [submitQuote, linkEscrow_quoted]
    minus: [linkEscrow_direct]
```

## Face Rules

Each face is a formal difference of two directed paths with identical
endpoints.

Validation rules:

- `plus` must be a contiguous directed path
- `minus` must be a contiguous directed path
- both paths must start at the same state
- both paths must end at the same state
- every named edge must exist in `transitions`

The face stalk is computed automatically as the ordered intersection of all
edge stalks appearing in the boundary.

## Public Output Contract

### Human output

`python3 h1_lint.py --2complex` reports:

- `H¹`, `H⁰`, `C⁰`, `C¹`, `rank(delta_0)` for the `1-complex`
- `H¹`, `H²`, `C⁰`, `C¹`, `C²`, `rank(delta_0)`, `rank(delta_1)`, `dim ker(delta_1)` for the `2-complex`
- the number of faces and `max|delta_1 delta_0|`
- named-path diagnostics

### JSON output

`python3 h1_lint.py --json --2complex` emits:

```json
{
  "protocol": "ACTP v2.7.0",
  "full": {
    "h0": 18,
    "h1": 24,
    "c0": 66,
    "c1": 72,
    "rank_delta0": 48,
    "status": "warn"
  },
  "two_complex": {
    "h0": 18,
    "h1": 0,
    "h2": 20,
    "c0": 66,
    "c1": 72,
    "c2": 44,
    "rank_delta0": 48,
    "rank_delta1": 24,
    "ker_delta1": 48,
    "complex_residual": 0.0,
    "status": "pass"
  }
}
```

## Bundled ACTP Result

For the shipped `protocol.yaml`:

- `1-complex`: `C⁰ = 66`, `C¹ = 72`, `rank(delta_0) = 48`, `H¹ = 24`
- `2-complex`: `C² = 44`, `rank(delta_1) = 24`, `ker(delta_1) = 48`, `H¹ = 0`, `H² = 20`

The public artifact therefore reproduces both the reduced-basis graph
diagnostics and the explicit face-level completeness result.

## Architecture

- `h1_lint.py` — CLI entry point, YAML validation, reporting
- `h1_engine.py` — `delta_0`, `delta_1`, and cohomology computations
- `protocol.yaml` — default ACTP model with explicit faces

## Design Decisions

- YAML remains the public interface
- face construction is explicit rather than inferred heuristically
- `1-complex` and `2-complex` are kept side-by-side because they serve different purposes
- named path expectations drive CI only when the YAML sets `expect_h1`
