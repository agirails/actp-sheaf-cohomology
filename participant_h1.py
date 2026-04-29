#!/usr/bin/env python3
"""
Higher-order participant sheaf supplement for ACTP.

This script models participants as vertices, information channels as edges,
and public-information triangles as 2-cells. It computes participant H¹ for:

1. The exact six-channel graph-only K4 participant complex.
2. A higher-order six-channel 2-complex with explicit public-information faces.

The goal is not to replace the paper's conservative four-channel upper-bound
diagnostic. Instead, it makes the "exact six-channel raw-visibility" question
reproducible and shows how strongly the answer depends on whether public
information cycles are left unfilled or explicitly completed.

Visibility model:
- Public on-chain state is visible to all principals via getTransaction(),
  public escrow mappings, and emitted events.
- Off-chain semantic payload content is bilateral between Requester and
  Provider unless separately anchored.
- Calldata decoding is treated as out of scope for the base exact model.
- Optional EAS-attestation content is also omitted from the base exact model;
  the paper already discusses that visibility as a separate caveat.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List

from h1_engine import analyse_protocol, analyse_protocol_2complex


PARTICIPANTS = ["Requester", "Provider", "EscrowVault", "ACTPKernel"]

CHANNELS = [
    {"from": "Requester", "to": "Provider", "name": "c1_rp"},
    {"from": "Requester", "to": "ACTPKernel", "name": "c2_rk"},
    {"from": "Provider", "to": "ACTPKernel", "name": "c3_pk"},
    {"from": "EscrowVault", "to": "ACTPKernel", "name": "c4_vk"},
    {"from": "Requester", "to": "EscrowVault", "name": "c5_rv"},
    {"from": "Provider", "to": "EscrowVault", "name": "c6_pv"},
]

# The full 2-skeleton on K4. A dimension contributes to a face only when it is
# visible on every edge of that triangle, so public dimensions are completed
# while bilateral semantic payloads are not.
PUBLIC_FACES = [
    {"name": "requester_provider_kernel", "plus": ["c1_rp", "c3_pk"], "minus": ["c2_rk"]},
    {"name": "requester_provider_vault", "plus": ["c1_rp", "c6_pv"], "minus": ["c5_rv"]},
    {"name": "requester_vault_kernel", "plus": ["c5_rv", "c4_vk"], "minus": ["c2_rk"]},
    {"name": "provider_vault_kernel", "plus": ["c6_pv", "c4_vk"], "minus": ["c3_pk"]},
]


def _all_participants(public_dims: List[str]) -> Dict[str, List[str]]:
    return {participant: list(public_dims) for participant in PARTICIPANTS}


def _add_dims(
    stalks: Dict[str, List[str]],
    participant: str,
    dims: List[str],
) -> None:
    stalks[participant].extend(dims)


def build_state_models() -> Dict[str, Dict[str, List[str]]]:
    """Exact six-channel raw-visibility participant models per ACTP state."""
    models: Dict[str, Dict[str, List[str]]] = {}

    initiated = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "created_at_public",
        "deadline_public",
        "service_hash_public",
    ])
    _add_dims(initiated, "Requester", ["task_spec_content"])
    _add_dims(initiated, "Provider", ["task_spec_content"])
    _add_dims(initiated, "ACTPKernel", ["kernel_transition_bookkeeping"])
    models["INITIATED"] = initiated

    quoted = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "created_at_public",
        "deadline_public",
        "service_hash_public",
        "quote_hash_public",
    ])
    _add_dims(quoted, "Requester", ["task_spec_content", "quote_terms_content"])
    _add_dims(quoted, "Provider", ["task_spec_content", "quote_terms_content"])
    _add_dims(quoted, "ACTPKernel", ["kernel_transition_bookkeeping"])
    models["QUOTED"] = quoted

    committed = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "deadline_public",
        "service_hash_public",
        "quote_hash_public",
        "escrow_contract_public",
        "escrow_id_public",
        "updated_at_public",
        "vault_balance_public",
        "platform_fee_bps_public",
    ])
    _add_dims(committed, "Requester", ["task_spec_content", "quote_terms_content"])
    _add_dims(committed, "Provider", ["task_spec_content", "quote_terms_content"])
    _add_dims(committed, "ACTPKernel", ["kernel_transition_bookkeeping", "fee_split_logic"])
    models["COMMITTED"] = committed

    in_progress = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "deadline_public",
        "service_hash_public",
        "quote_hash_public",
        "escrow_contract_public",
        "escrow_id_public",
        "updated_at_public",
        "work_started_at_public",
        "vault_balance_public",
        "platform_fee_bps_public",
    ])
    _add_dims(in_progress, "Requester", ["task_spec_content", "quote_terms_content", "work_context_content"])
    _add_dims(in_progress, "Provider", ["task_spec_content", "quote_terms_content", "work_context_content"])
    _add_dims(in_progress, "ACTPKernel", ["kernel_transition_bookkeeping", "fee_split_logic"])
    models["IN_PROGRESS"] = in_progress

    delivered = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "deadline_public",
        "service_hash_public",
        "quote_hash_public",
        "escrow_contract_public",
        "escrow_id_public",
        "updated_at_public",
        "work_started_at_public",
        "dispute_window_public",
        "vault_balance_public",
        "platform_fee_bps_public",
    ])
    _add_dims(delivered, "Requester", ["task_spec_content", "quote_terms_content", "delivery_metadata_content"])
    _add_dims(delivered, "Provider", ["task_spec_content", "quote_terms_content", "delivery_metadata_content"])
    _add_dims(delivered, "ACTPKernel", ["kernel_transition_bookkeeping", "fee_split_logic"])
    models["DELIVERED"] = delivered

    settled = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "service_hash_public",
        "quote_hash_public",
        "escrow_contract_public",
        "escrow_id_public",
        "updated_at_public",
        "provider_payout_public",
        "platform_fee_public",
        "settlement_event_public",
    ])
    _add_dims(settled, "Requester", ["task_spec_content", "quote_terms_content", "delivery_metadata_content"])
    _add_dims(settled, "Provider", ["task_spec_content", "quote_terms_content", "delivery_metadata_content"])
    _add_dims(settled, "ACTPKernel", ["kernel_transition_bookkeeping", "fee_split_logic", "settlement_accounting_logic"])
    models["SETTLED"] = settled

    disputed = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "deadline_public",
        "service_hash_public",
        "quote_hash_public",
        "escrow_contract_public",
        "escrow_id_public",
        "updated_at_public",
        "work_started_at_public",
        "dispute_window_public",
        "dispute_initiator_public",
        "dispute_bond_public",
        "vault_balance_public",
    ])
    _add_dims(
        disputed,
        "Requester",
        ["task_spec_content", "quote_terms_content", "delivery_metadata_content", "dispute_reason_content", "dispute_evidence_content"],
    )
    _add_dims(
        disputed,
        "Provider",
        ["task_spec_content", "quote_terms_content", "delivery_metadata_content", "provider_counterevidence_content"],
    )
    _add_dims(disputed, "ACTPKernel", ["kernel_transition_bookkeeping", "dispute_resolution_logic"])
    models["DISPUTED"] = disputed

    cancelled = _all_participants([
        "tx_id",
        "requester_addr",
        "provider_addr",
        "state_flag",
        "amount_public",
        "updated_at_public",
        "refund_event_public",
    ])
    _add_dims(cancelled, "Requester", ["task_spec_content", "cancellation_reason_content"])
    _add_dims(cancelled, "Provider", ["task_spec_content", "cancellation_reason_content"])
    _add_dims(cancelled, "ACTPKernel", ["kernel_transition_bookkeeping", "cancellation_auth_logic"])
    models["CANCELLED"] = cancelled

    return models


def build_report() -> Dict[str, object]:
    models = build_state_models()
    per_state = {}

    for state_name, stalks in models.items():
        graph = analyse_protocol(stalks, CHANNELS)
        higher = analyse_protocol_2complex(stalks, CHANNELS, PUBLIC_FACES)
        per_state[state_name] = {
            "c0": graph["dim_c0"],
            "c1": graph["dim_c1"],
            "graph_h1": graph["dim_h1"],
            "graph_h0": graph["dim_h0"],
            "c2": higher["dim_c2"],
            "higher_h1": higher["dim_h1"],
            "higher_h0": higher["dim_h0"],
            "higher_h2": higher["dim_h2"],
            "rank_delta0": higher["rank_delta0"],
            "rank_delta1": higher["rank_delta1"],
            "complex_residual": higher["complex_residual"],
        }

    return {
        "complex": {
            "participants": PARTICIPANTS,
            "channels": [channel["name"] for channel in CHANNELS],
            "faces": [face["name"] for face in PUBLIC_FACES],
        },
        "states": per_state,
    }


def print_human(report: Dict[str, object]) -> None:
    print()
    print("ACTP PARTICIPANT H1 SUPPLEMENT")
    print("=" * 36)
    print()
    print("Six-channel raw-visibility participant complex:")
    print(f"  vertices : {', '.join(report['complex']['participants'])}")
    print(f"  channels : {', '.join(report['complex']['channels'])}")
    print(f"  faces    : {', '.join(report['complex']['faces'])}")
    print()
    print("Per-state results")
    print("  state        graph H1   higher-order H1   H2   C2")
    for state_name, result in report["states"].items():
        print(
            f"  {state_name:12s} {result['graph_h1']:8d} {result['higher_h1']:17d}"
            f" {result['higher_h2']:4d} {result['c2']:4d}"
        )
    print()
    print("Interpretation")
    print("  graph H1        : six-channel K4 without public-information faces")
    print("  higher-order H1 : same participant model after explicit public-face completion")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute higher-order ACTP participant H1.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable output")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
