"""
H¹ Sheaf Cohomology for ACTP Protocol Verification
====================================================

Constructs a cellular sheaf over the ACTP 8-state lifecycle and computes
the first cohomology group H¹ to measure protocol completeness.

Mathematical Framework:
- Vertices (V): ACTP states (INITIATED, QUOTED, COMMITTED, ...)
- Edges (E): Valid state transitions
- Stalks F(v): Vector space of observable data at each state
- Stalks F(e): Vector space of shared/comparable data along each transition
- Restriction maps: How local data at a vertex projects onto an edge

H¹ = ker(δ₁) / im(δ₀)
- δ₀: C⁰ → C¹ (coboundary from vertices to edges)
- δ₁: C¹ → C² (coboundary from edges to faces/2-cells)

For a graph (no 2-cells), H¹ = C¹ / im(δ₀)
dim(H¹) = dim(C¹) - rank(δ₀) = |E| - rank(δ₀)

If dim(H¹) = 0: all local views globalise — protocol is topologically complete.
If dim(H¹) > 0: there are obstructions — gaps where local data fails to cohere.

Note: Archival exploratory script retained for reference. The current
canonical implementation is split into h1_engine.py (computation) and
h1_lint.py (CLI).

References:
  - Felber et al. (2025) arXiv:2503.02556
  - Ghrist, "Elementary Applied Topology"
  - AGIRAILS SDK v2.7.0 specification
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import IntEnum


# ─── ACTP State Machine ───────────────────────────────────────────────

class ACTPState(IntEnum):
    INITIATED = 0
    QUOTED = 1
    COMMITTED = 2
    IN_PROGRESS = 3
    DELIVERED = 4
    SETTLED = 5
    DISPUTED = 6
    CANCELLED = 7


# Valid transitions from the ACTP specification
# Each tuple: (source_state, target_state, transition_name)
ACTP_TRANSITIONS = [
    (ACTPState.INITIATED, ACTPState.QUOTED, "submitQuote"),
    (ACTPState.INITIATED, ACTPState.COMMITTED, "linkEscrow_direct"),
    (ACTPState.QUOTED, ACTPState.COMMITTED, "linkEscrow_quoted"),
    (ACTPState.COMMITTED, ACTPState.IN_PROGRESS, "startWork"),
    (ACTPState.IN_PROGRESS, ACTPState.DELIVERED, "deliver"),
    (ACTPState.DELIVERED, ACTPState.SETTLED, "settle"),
    (ACTPState.DELIVERED, ACTPState.DISPUTED, "dispute"),
    (ACTPState.DISPUTED, ACTPState.SETTLED, "resolveDispute"),
    # Cancellation paths
    (ACTPState.INITIATED, ACTPState.CANCELLED, "cancel_initiated"),
    (ACTPState.QUOTED, ACTPState.CANCELLED, "cancel_quoted"),
    (ACTPState.COMMITTED, ACTPState.CANCELLED, "cancel_committed"),
    (ACTPState.IN_PROGRESS, ACTPState.CANCELLED, "cancel_in_progress"),
]


# ─── Stalk Definitions ───────────────────────────────────────────────
#
# Each state has observable data dimensions. These represent the information
# available to participants at that state.
#
# Kira's Q1: "What constitutes stalk data?"
# Answer: State enum + escrow status + attestation + delivery proof + amounts
#
# We model each dimension as a basis vector in the stalk space.

@dataclass
class StalkDefinition:
    """Defines the data observable at a vertex (state) or along an edge (transition)."""
    dimensions: List[str]
    dim: int = field(init=False)

    def __post_init__(self):
        self.dim = len(self.dimensions)


# Vertex stalks: what data exists at each ACTP state
VERTEX_STALKS: Dict[ACTPState, StalkDefinition] = {
    ACTPState.INITIATED: StalkDefinition([
        "transaction_id",       # Created by requester
        "requester_address",    # Known
        "provider_address",     # Known
        "amount",               # Agreed
        "deadline",             # Set
        "service_hash",         # What's being purchased
    ]),
    ACTPState.QUOTED: StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",               # May be updated by quote
        "deadline",
        "service_hash",
        "quote_details",        # Provider's price/terms
    ]),
    ACTPState.COMMITTED: StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "deadline",
        "service_hash",
        "escrow_id",            # USDC locked in vault
        "escrow_balance",       # Verifiable on-chain
    ]),
    ACTPState.IN_PROGRESS: StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "deadline",
        "service_hash",
        "escrow_id",
        "escrow_balance",
        "work_started_at",      # Timestamp
    ]),
    ACTPState.DELIVERED: StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "deadline",
        "service_hash",
        "escrow_id",
        "escrow_balance",
        "work_started_at",
        "delivery_proof",       # Provider's claim of completion
        "dispute_window_end",   # When auto-settlement kicks in
    ]),
    ACTPState.SETTLED: StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "service_hash",
        "escrow_id",
        "settlement_tx",        # On-chain settlement receipt
        "provider_payout",      # Amount received
        "platform_fee",         # Fee taken
    ]),
    ACTPState.DISPUTED: StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "deadline",
        "service_hash",
        "escrow_id",
        "escrow_balance",
        "delivery_proof",       # Provider says delivered
        "dispute_reason",       # Requester says not delivered
        # NOTE: Without attestation, these two views may be irreconcilable
        # This is where H¹ ≠ 0 might appear
    ]),
    ACTPState.CANCELLED: StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "cancellation_reason",
        "refund_tx",            # Escrow returned (if was committed)
    ]),
}


# ─── Restriction Maps ────────────────────────────────────────────────
#
# For each edge (transition), we define which dimensions of the source
# and target vertex stalks are "shared" — i.e., must agree for the
# transition to be consistent.
#
# The restriction map ρ_{v→e} projects vertex stalk F(v) onto edge stalk F(e).
# If both endpoints of an edge agree on the shared dimensions, the local
# sections are compatible.

def build_restriction_maps():
    """
    Build restriction maps for each transition.

    For each edge (s, t, name), we identify the shared dimensions between
    source and target. The edge stalk F(e) = intersection of observable
    data at both endpoints.

    Returns dict of edge_name -> (source_projection, target_projection)
    where each projection is a matrix mapping vertex stalk -> edge stalk.
    """
    restrictions = {}

    for source, target, name in ACTP_TRANSITIONS:
        source_dims = VERTEX_STALKS[source].dimensions
        target_dims = VERTEX_STALKS[target].dimensions

        # Shared dimensions = intersection (data that must be consistent)
        shared = [d for d in source_dims if d in target_dims]

        if not shared:
            # No shared data = trivially consistent (edge stalk is 0-dim)
            restrictions[name] = {
                'shared': [],
                'source_proj': np.zeros((0, len(source_dims))),
                'target_proj': np.zeros((0, len(target_dims))),
            }
            continue

        # Build projection matrices
        source_proj = np.zeros((len(shared), len(source_dims)))
        target_proj = np.zeros((len(shared), len(target_dims)))

        for i, dim_name in enumerate(shared):
            source_proj[i, source_dims.index(dim_name)] = 1.0
            target_proj[i, target_dims.index(dim_name)] = 1.0

        restrictions[name] = {
            'shared': shared,
            'source_proj': source_proj,
            'target_proj': target_proj,
        }

    return restrictions


# ─── Coboundary Map δ₀ ───────────────────────────────────────────────
#
# δ₀: C⁰(F) → C¹(F)
# Maps global sections (assignments of vectors to all vertices) to
# cochains on edges (measuring inconsistency at each transition).
#
# For edge e = (u, v):
#   (δ₀ f)(e) = ρ_{v→e}(f(v)) - ρ_{u→e}(f(u))
#
# If δ₀ f = 0 for all edges, then f is a global section (all local
# views are consistent).

def build_coboundary_0(restrictions: dict) -> np.ndarray:
    """
    Build the coboundary map δ₀: C⁰ → C¹.

    C⁰ = direct sum of all vertex stalks = ⊕ F(v)
    C¹ = direct sum of all edge stalks = ⊕ F(e)

    δ₀ is a matrix of size (dim C¹) × (dim C⁰).
    """
    # Compute dimensions
    vertex_dims = {state: VERTEX_STALKS[state].dim for state in ACTPState}
    vertex_offsets = {}
    offset = 0
    for state in ACTPState:
        vertex_offsets[state] = offset
        offset += vertex_dims[state]
    total_c0 = offset

    edge_dims = {}
    edge_offsets = {}
    offset = 0
    for source, target, name in ACTP_TRANSITIONS:
        d = len(restrictions[name]['shared'])
        edge_dims[name] = d
        edge_offsets[name] = offset
        offset += d
    total_c1 = offset

    # Build δ₀
    delta_0 = np.zeros((total_c1, total_c0))

    for source, target, name in ACTP_TRANSITIONS:
        r = restrictions[name]
        shared_dim = len(r['shared'])
        if shared_dim == 0:
            continue

        e_off = edge_offsets[name]
        s_off = vertex_offsets[source]
        t_off = vertex_offsets[target]

        # (δ₀ f)(e) = ρ_{target→e}(f(target)) - ρ_{source→e}(f(source))
        delta_0[e_off:e_off + shared_dim, t_off:t_off + vertex_dims[target]] += r['target_proj']
        delta_0[e_off:e_off + shared_dim, s_off:s_off + vertex_dims[source]] -= r['source_proj']

    return delta_0


# ─── H¹ Computation ──────────────────────────────────────────────────
#
# For a graph (1-dimensional cell complex with no 2-cells):
#   H¹ = C¹ / im(δ₀)
#   dim(H¹) = dim(C¹) - rank(δ₀)
#
# If we add 2-cells (cycles in the state machine), then:
#   H¹ = ker(δ₁) / im(δ₀)
# But for the ACTP DAG (mostly acyclic), the graph computation suffices.

def compute_h1(delta_0: np.ndarray) -> dict:
    """
    Compute H¹ = C¹ / im(δ₀).

    Returns:
        dim_c0: dimension of C⁰
        dim_c1: dimension of C¹
        rank_delta0: rank of δ₀
        dim_h0: dimension of H⁰ = ker(δ₀)
        dim_h1: dimension of H¹ = dim(C¹) - rank(δ₀)
        euler: Euler characteristic = dim(H⁰) - dim(H¹)
    """
    dim_c1, dim_c0 = delta_0.shape
    rank = np.linalg.matrix_rank(delta_0, tol=1e-10)

    dim_h0 = dim_c0 - rank  # ker(δ₀)
    dim_h1 = dim_c1 - rank   # coker(δ₀) for graphs

    return {
        'dim_c0': dim_c0,
        'dim_c1': dim_c1,
        'rank_delta0': rank,
        'dim_h0': dim_h0,
        'dim_h1': dim_h1,
        'euler': dim_h0 - dim_h1,
    }


# ─── Analysis: Per-State H¹ ──────────────────────────────────────────
#
# Kira's Q2: Does the DISPUTED state specifically contribute to H¹ ≠ 0?
# We can compute H¹ for subgraphs to isolate which states/transitions
# contribute obstructions.

def compute_subgraph_h1(include_states: set, include_transitions: list = None):
    """Compute H¹ for a subgraph of the ACTP state machine."""
    if include_transitions is None:
        include_transitions = [
            (s, t, n) for s, t, n in ACTP_TRANSITIONS
            if s in include_states and t in include_states
        ]

    # Rebuild stalks and restrictions for subgraph
    sub_restrictions = build_restriction_maps()

    vertex_dims = {state: VERTEX_STALKS[state].dim for state in include_states}
    vertex_offsets = {}
    offset = 0
    for state in sorted(include_states, key=int):
        vertex_offsets[state] = offset
        offset += vertex_dims[state]
    total_c0 = offset

    edge_dims = {}
    edge_offsets = {}
    offset = 0
    for source, target, name in include_transitions:
        d = len(sub_restrictions[name]['shared'])
        edge_dims[name] = d
        edge_offsets[name] = offset
        offset += d
    total_c1 = offset

    if total_c1 == 0 or total_c0 == 0:
        return {'dim_c0': total_c0, 'dim_c1': total_c1, 'rank_delta0': 0,
                'dim_h0': total_c0, 'dim_h1': 0, 'euler': total_c0}

    delta_0 = np.zeros((total_c1, total_c0))

    for source, target, name in include_transitions:
        r = sub_restrictions[name]
        shared_dim = len(r['shared'])
        if shared_dim == 0:
            continue

        e_off = edge_offsets[name]
        s_off = vertex_offsets[source]
        t_off = vertex_offsets[target]

        delta_0[e_off:e_off + shared_dim, t_off:t_off + vertex_dims[target]] += r['target_proj']
        delta_0[e_off:e_off + shared_dim, s_off:s_off + vertex_dims[source]] -= r['source_proj']

    return compute_h1(delta_0)


# ─── EAS Attestation Layer (Kira's Q2) ───────────────────────────────
#
# What if we add EAS attestation data to the DISPUTED state?
# Does the additional information close the cohomological gap?

def compute_with_attestation():
    """
    Re-compute H¹ with EAS attestation added across the dispute lifecycle.

    Kira's hypothesis: base state machine has H¹ ≠ 0 at DISPUTED,
    but attestation layer closes the gap.

    Key insight: attestation data must BRIDGE states — appearing in
    DELIVERED (where proof originates), DISPUTED (where it's contested),
    and SETTLED (where resolution is recorded). Only shared dimensions
    create cohomological connections.
    """
    # Save originals
    original_delivered = VERTEX_STALKS[ACTPState.DELIVERED]
    original_disputed = VERTEX_STALKS[ACTPState.DISPUTED]
    original_settled = VERTEX_STALKS[ACTPState.SETTLED]

    # Augment DELIVERED with attestation (proof created at delivery)
    VERTEX_STALKS[ACTPState.DELIVERED] = StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "deadline",
        "service_hash",
        "escrow_id",
        "escrow_balance",
        "work_started_at",
        "delivery_proof",
        "dispute_window_end",
        # Attestation: created at delivery time
        "attestation_uid",          # EAS attestation of delivery
        "attestation_data",         # Structured proof (timestamps, hashes, outputs)
    ])

    # Augment DISPUTED with attestation (contested but verifiable)
    VERTEX_STALKS[ACTPState.DISPUTED] = StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "deadline",
        "service_hash",
        "escrow_id",
        "escrow_balance",
        "delivery_proof",
        "dispute_reason",
        # Attestation: the verifiable bridge
        "attestation_uid",          # Same as DELIVERED — this is the shared dim!
        "attestation_data",         # Same structured proof — verifiable on-chain
        "resolution_proof",         # Encodes resolution split
    ])

    # Augment SETTLED with attestation trail
    VERTEX_STALKS[ACTPState.SETTLED] = StalkDefinition([
        "transaction_id",
        "requester_address",
        "provider_address",
        "amount",
        "service_hash",
        "escrow_id",
        "settlement_tx",
        "provider_payout",
        "platform_fee",
        # Attestation: carried through resolution
        "attestation_uid",          # Preserved from dispute
        "attestation_data",         # Preserved — full audit trail
        "resolution_proof",         # How it was resolved
    ])

    restrictions = build_restriction_maps()
    delta_0 = build_coboundary_0(restrictions)
    result = compute_h1(delta_0)

    # Restore originals
    VERTEX_STALKS[ACTPState.DELIVERED] = original_delivered
    VERTEX_STALKS[ACTPState.DISPUTED] = original_disputed
    VERTEX_STALKS[ACTPState.SETTLED] = original_settled

    return result


# ─── Main Execution ──────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("H¹ SHEAF COHOMOLOGY — ACTP PROTOCOL VERIFICATION")
    print("=" * 70)
    print()

    # ── Step 1: Full state machine ──
    print("─── STEP 1: Full ACTP State Machine (Base Protocol) ───")
    print()

    for state in ACTPState:
        stalk = VERTEX_STALKS[state]
        print(f"  {state.name:15s}  dim(F) = {stalk.dim:2d}  dims: {stalk.dimensions}")
    print()

    restrictions = build_restriction_maps()

    print("  Transitions:")
    for source, target, name in ACTP_TRANSITIONS:
        r = restrictions[name]
        print(f"    {source.name:15s} → {target.name:15s}  ({name:25s})  "
              f"shared dims: {len(r['shared'])}")
    print()

    delta_0 = build_coboundary_0(restrictions)
    result = compute_h1(delta_0)

    print(f"  δ₀ matrix: {delta_0.shape[0]} × {delta_0.shape[1]}")
    print(f"  dim(C⁰) = {result['dim_c0']}  (total vertex stalk dimensions)")
    print(f"  dim(C¹) = {result['dim_c1']}  (total edge stalk dimensions)")
    print(f"  rank(δ₀) = {result['rank_delta0']}")
    print()
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║  dim(H⁰) = {result['dim_h0']:3d}  (global sections)  ║")
    print(f"  ║  dim(H¹) = {result['dim_h1']:3d}  (obstructions)     ║")
    print(f"  ║  χ (Euler) = {result['euler']:3d}                    ║")
    print(f"  ╚══════════════════════════════════════╝")
    print()

    if result['dim_h1'] == 0:
        print("  ✅ H¹ = 0 — Protocol is TOPOLOGICALLY COMPLETE.")
        print("     All local views globalise. Zero trust obstructions.")
    else:
        print(f"  ⚠️  H¹ ≠ 0 — {result['dim_h1']} independent obstruction(s) detected.")
        print("     There exist local views that cannot be reconciled by protocol alone.")
    print()

    # ── Step 2: Dispute subgraph analysis ──
    print("─── STEP 2: Dispute Path Analysis ───")
    print("  Subgraph: DELIVERED → DISPUTED → SETTLED")
    print()

    dispute_states = {ACTPState.DELIVERED, ACTPState.DISPUTED, ACTPState.SETTLED}
    dispute_result = compute_subgraph_h1(dispute_states)

    print(f"  dim(C⁰) = {dispute_result['dim_c0']}")
    print(f"  dim(C¹) = {dispute_result['dim_c1']}")
    print(f"  rank(δ₀) = {dispute_result['rank_delta0']}")
    print(f"  dim(H¹) = {dispute_result['dim_h1']}")
    print()

    if dispute_result['dim_h1'] > 0:
        print(f"  ⚠️  Dispute path has {dispute_result['dim_h1']} obstruction(s).")
        print("     This is where trust is currently required (admin resolution).")
    else:
        print("  ✅ Dispute path: H¹ = 0")
    print()

    # ── Step 3: Happy path analysis ──
    print("─── STEP 3: Happy Path Analysis ───")
    print("  Subgraph: INITIATED → COMMITTED → IN_PROGRESS → DELIVERED → SETTLED")
    print()

    happy_states = {ACTPState.INITIATED, ACTPState.COMMITTED,
                    ACTPState.IN_PROGRESS, ACTPState.DELIVERED, ACTPState.SETTLED}
    happy_result = compute_subgraph_h1(happy_states)

    print(f"  dim(H¹) = {happy_result['dim_h1']}")
    if happy_result['dim_h1'] == 0:
        print("  ✅ Happy path: H¹ = 0 — No obstructions on the normal flow.")
    print()

    # ── Step 4: With EAS Attestation (Kira's Q2) ──
    print("─── STEP 4: With EAS Attestation Layer (Kira's Q2) ───")
    print("  Adding attestation_uid, attestation_schema, attestation_data,")
    print("  attestation_timestamp, resolution_proof to DISPUTED + SETTLED stalks")
    print()

    eas_result = compute_with_attestation()

    print(f"  dim(C⁰) = {eas_result['dim_c0']}  (expanded stalks)")
    print(f"  dim(C¹) = {eas_result['dim_c1']}")
    print(f"  rank(δ₀) = {eas_result['rank_delta0']}")
    print(f"  dim(H¹) = {eas_result['dim_h1']}")
    print()

    base_h1 = result['dim_h1']
    eas_h1 = eas_result['dim_h1']
    delta = base_h1 - eas_h1

    if delta > 0:
        print(f"  🔑 EAS attestation CLOSES {delta} obstruction(s)!")
        print(f"     Base protocol: H¹ = {base_h1}")
        print(f"     With attestation: H¹ = {eas_h1}")
        if eas_h1 == 0:
            print("     ✅ Attestation layer makes protocol topologically complete.")
            print()
            print("     This confirms Kira's hypothesis:")
            print("     'The base state machine has H¹ ≠ 0, but EAS closes the gap.'")
            print("     The mathematics DROVE the design. Not just validated it.")
        else:
            print(f"     ⚠️  {eas_h1} obstruction(s) remain even with attestation.")
    elif base_h1 == 0:
        print("  Base protocol already has H¹ = 0. Attestation doesn't change topology.")
    else:
        print("  ⚠️  Attestation does not reduce obstructions.")
    print()

    # ── Summary ──
    print("═" * 70)
    print("SUMMARY")
    print("═" * 70)
    print(f"  Full protocol (base):        H¹ = {result['dim_h1']}")
    print(f"  Happy path only:             H¹ = {happy_result['dim_h1']}")
    print(f"  Dispute path only:           H¹ = {dispute_result['dim_h1']}")
    print(f"  Full protocol + attestation: H¹ = {eas_result['dim_h1']}")
    print()
    print("  Interpretation:")
    if result['dim_h1'] > 0 and eas_result['dim_h1'] < result['dim_h1']:
        print("  → Base protocol has structural gaps in dispute resolution.")
        print("  → EAS attestation layer was engineered to close those gaps.")
        print("  → The topology proves the design intent, not just the code.")
    elif result['dim_h1'] == 0:
        print("  → Protocol is already topologically complete.")
        print("  → No trust obstructions exist in any reachable state.")
    print()


if __name__ == "__main__":
    main()
