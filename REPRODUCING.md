# Reproducing the Paper Results

All commands assume you are in this directory (`H1 paper/h1-research/`).

## Setup

```bash
pip install -r requirements.txt   # numpy, pyyaml
```

## State-Based Sheaf (Sections 3-4)

### 1-Complex H¹ = 24 and subgraph breakdown (Table 2)
```bash
python3 h1_lint.py --config protocol.yaml
```

**Note on "Quoted linear path" row in Table 2:** The linter's `happy_quoted` path
includes both the direct commit edge (e2) and the quoted commit edge (e1→e4),
producing the "Quote/commit comparison" result (H¹=6). The pure quoted linear
path (INIT→QUOT→COMM→INPROG→DELIV→SETTL without e2) is not separately defined
in protocol.yaml because the engine's path model uses state sets, not edge sets.
The row's values (C⁰=50, C¹=35, H¹=0) follow by construction: a linear path
(tree) has no cycles, so H¹=0 unconditionally.

### 2-Complex H¹ = 0 (Theorem 3.6, Table 3)
```bash
python3 h1_lint.py --config protocol.yaml --2complex
```
Expected: `H^1 = 0`, `C^0 = 66`, `C^1 = 72`, `C^2 = 44`, `rank(delta_0) = 48`, `rank(delta_1) = 24`.

### Rational arithmetic cross-validation (Section 3.2)
```bash
python3 verify_rational.py
```
Expected: `ALL CROSS-VALIDATIONS PASSED`

## Participant-Based Sheaf (Section 5)

### Conservative 4-channel semantic model (Table 4, Proposition 5.1)
```bash
python3 participant_semantic_h1.py
```
Expected: H¹ ∈ [6, 8] at every state.

### Exact 6-channel raw-visibility model (Appendix E)
```bash
python3 participant_h1.py
```
Expected: H¹ = 0 at every state (higher-order column).

## Toy Protocols (Section 8, "Generality beyond ACTP")

### Clean 3-state escrow (H¹ = 0)
```bash
python3 h1_lint.py --config toy_escrow_protocol.yaml
```

### Broken 4-state escrow with dispute cycle (H¹ = 4)
```bash
python3 h1_lint.py --config toy_escrow_broken.yaml
```

## File Manifest

| File | Paper reference | Purpose |
|------|----------------|---------|
| `protocol.yaml` | Tables 1-3, Theorem 3.6 | ACTP v2.7 protocol definition with 10 faces |
| `h1_engine.py` | Section 6.2 | Core sheaf computation engine |
| `h1_lint.py` | Section 6.3 | CI-ready linter with --2complex, --diff, --leaks |
| `participant_semantic_h1.py` | Table 4, Appendix D | Conservative 4-channel participant model |
| `participant_h1.py` | Appendix E | Exact 6-channel raw-visibility model |
| `verify_rational.py` | Section 3.2 | Exact rational arithmetic cross-validation |
| `actp_sheaf.py` | Section 6 | Original reference implementation |
| `toy_escrow_protocol.yaml` | Section 8 | 3-state toy (methodology validation) |
| `toy_escrow_broken.yaml` | Section 8 | 4-state broken toy (gap detection test) |
| `requirements.txt` | — | Python dependencies |
