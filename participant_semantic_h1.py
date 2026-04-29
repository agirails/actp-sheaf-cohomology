#!/usr/bin/env python3
"""
Conservative semantic participant sheaf supplement for ACTP.

This script formalizes the participant model used in the paper's Section 5:

- participants are vertices
- four conservative semantic channels are edges
- stalk dimensions are semantic observables, not raw storage slots

The point of this artifact is reproducibility. It turns the paper's
conservative four-channel participant table from prose into runnable linear
algebra. Unlike participant_h1.py, which studies exact six-channel
raw-visibility, this script models semantic asymmetry directly.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List

from h1_engine import analyse_protocol


PARTICIPANTS = ["Requester", "Provider", "EscrowVault", "ACTPKernel"]

SEMANTIC_CHANNELS = [
    {"from": "Requester", "to": "Provider", "name": "c1_rp"},
    {"from": "Requester", "to": "ACTPKernel", "name": "c2_rk"},
    {"from": "Provider", "to": "ACTPKernel", "name": "c3_pk"},
    {"from": "EscrowVault", "to": "ACTPKernel", "name": "c4_vk"},
]


def _stalks(
    common_rpk: List[str],
    requester_only: List[str],
    provider_only: List[str],
    shared_rp: List[str],
    shared_vk: List[str],
    kernel_only: List[str],
    vault_only: List[str],
) -> Dict[str, List[str]]:
    """
    Build vertex stalks for one protocol state.

    `common_rpk` are semantic references visible on the Requester/Provider/
    Kernel triangle. In this conservative model, each such shared semantic
    reference contributes one obstruction dimension on the 4-edge graph.
    """
    return {
        "Requester": common_rpk + shared_rp + requester_only,
        "Provider": common_rpk + shared_rp + provider_only,
        "ACTPKernel": common_rpk + shared_vk + kernel_only,
        "EscrowVault": shared_vk + vault_only,
    }


def build_models() -> Dict[str, Dict[str, List[str]]]:
    models: Dict[str, Dict[str, List[str]]] = {}

    models["INITIATED"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "deadline_reference",
            "service_commitment_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "budget_negotiation_context",
        ],
        requester_only=["requester_private_intent"],
        provider_only=["provider_private_feasibility"],
        shared_vk=["vault_contract_reference", "escrow_status_reference"],
        kernel_only=["kernel_transition_bookkeeping"],
        vault_only=["vault_local_balance_view"],
    )

    models["QUOTED"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "deadline_reference",
            "service_commitment_reference",
            "quote_commitment_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "quote_terms_content",
            "acceptance_context",
        ],
        requester_only=["requester_private_acceptance_threshold"],
        provider_only=["provider_private_margin"],
        shared_vk=["vault_contract_reference", "escrow_status_reference"],
        kernel_only=["kernel_transition_bookkeeping"],
        vault_only=["vault_local_balance_view"],
    )

    models["COMMITTED"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "service_commitment_reference",
            "quote_commitment_reference",
            "escrow_linkage_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "quote_terms_content",
            "escrow_linkage_semantics",
        ],
        requester_only=["requester_private_settlement_expectation"],
        provider_only=["provider_private_delivery_plan"],
        shared_vk=[
            "vault_contract_reference",
            "escrow_status_reference",
            "vault_balance_reference",
        ],
        kernel_only=["kernel_transition_bookkeeping", "fee_split_logic"],
        vault_only=["vault_local_balance_view"],
    )

    models["IN_PROGRESS"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "service_commitment_reference",
            "escrow_linkage_reference",
            "work_started_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "quote_terms_content",
            "work_context_content",
            "progress_semantics_content",
        ],
        requester_only=["requester_private_monitoring_context"],
        provider_only=["provider_private_execution_context"],
        shared_vk=[
            "vault_contract_reference",
            "escrow_status_reference",
            "vault_balance_reference",
        ],
        kernel_only=["kernel_transition_bookkeeping", "fee_split_logic"],
        vault_only=["vault_local_balance_view"],
    )

    models["DELIVERED"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "service_commitment_reference",
            "escrow_linkage_reference",
            "work_started_reference",
            "dispute_window_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "quote_terms_content",
            "delivery_metadata_content",
            "delivery_evidence_content",
        ],
        requester_only=["requester_private_acceptance_basis"],
        provider_only=["provider_private_delivery_basis"],
        shared_vk=[
            "vault_contract_reference",
            "escrow_status_reference",
            "vault_balance_reference",
        ],
        kernel_only=["kernel_transition_bookkeeping", "fee_split_logic"],
        vault_only=["vault_local_balance_view"],
    )

    models["SETTLED"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "service_commitment_reference",
            "escrow_linkage_reference",
            "settlement_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "quote_terms_content",
            "settlement_semantics_content",
        ],
        requester_only=["requester_private_post_settlement_context"],
        provider_only=["provider_private_post_settlement_context"],
        shared_vk=[
            "vault_contract_reference",
            "vault_balance_reference",
            "release_status_reference",
        ],
        kernel_only=["kernel_transition_bookkeeping", "settlement_accounting_logic"],
        vault_only=["vault_local_release_view"],
    )

    models["DISPUTED"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "service_commitment_reference",
            "escrow_linkage_reference",
            "dispute_window_reference",
            "dispute_open_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "quote_terms_content",
            "delivery_metadata_content",
        ],
        requester_only=[
            "dispute_reason_content",
            "dispute_evidence_content",
        ],
        provider_only=[
            "provider_counterevidence_content",
            "provider_dispute_response_context",
        ],
        shared_vk=[
            "vault_contract_reference",
            "vault_balance_reference",
            "bond_reference",
        ],
        kernel_only=["kernel_transition_bookkeeping", "dispute_resolution_logic"],
        vault_only=["vault_local_bond_view"],
    )

    models["CANCELLED"] = _stalks(
        common_rpk=[
            "tx_reference",
            "requester_identity_reference",
            "provider_identity_reference",
            "amount_reference",
            "cancellation_reference",
            "refund_reference",
        ],
        shared_rp=[
            "task_spec_content",
            "cancellation_reason_content",
        ],
        requester_only=["requester_private_cancellation_context"],
        provider_only=["provider_private_cancellation_context"],
        shared_vk=[
            "vault_contract_reference",
            "vault_balance_reference",
        ],
        kernel_only=["kernel_transition_bookkeeping", "cancellation_auth_logic"],
        vault_only=["vault_local_refund_view"],
    )

    return models


EXPECTED_H1 = {
    "INITIATED": 6,
    "QUOTED": 7,
    "COMMITTED": 7,
    "IN_PROGRESS": 7,
    "DELIVERED": 8,
    "SETTLED": 7,
    "DISPUTED": 8,
    "CANCELLED": 6,
}


KEY_ASYMMETRY = {
    "INITIATED": "Off-chain task and budget negotiation remain bilateral",
    "QUOTED": "Quote semantics and acceptance are not uniformly replicated",
    "COMMITTED": "Escrow linkage semantics and timing are not fully shared as meaning",
    "IN_PROGRESS": "Progress semantics remain partly off-chain",
    "DELIVERED": "Delivery evidence and metadata are split across channels",
    "SETTLED": "Public settlement references do not exhaust settlement semantics",
    "DISPUTED": "Dispute rationale and evidence remain asymmetric",
    "CANCELLED": "Cancellation reason and refund semantics are not uniformly visible",
}


def build_report() -> Dict[str, object]:
    models = build_models()
    per_state = {}
    mismatches = []

    for state_name, stalks in models.items():
        result = analyse_protocol(stalks, SEMANTIC_CHANNELS)
        expected = EXPECTED_H1[state_name]
        if result["dim_h1"] != expected:
            mismatches.append({"state": state_name, "expected": expected, "actual": result["dim_h1"]})
        per_state[state_name] = {
            "h1": result["dim_h1"],
            "h0": result["dim_h0"],
            "c0": result["dim_c0"],
            "c1": result["dim_c1"],
            "rank_delta0": result["rank_delta0"],
            "expected_h1": expected,
            "key_asymmetry": KEY_ASYMMETRY[state_name],
        }

    return {
        "model": {
            "participants": PARTICIPANTS,
            "channels": [channel["name"] for channel in SEMANTIC_CHANNELS],
            "interpretation": "conservative semantic four-channel upper-bound participant model",
        },
        "states": per_state,
        "mismatches": mismatches,
    }


def print_human(report: Dict[str, object]) -> None:
    print()
    print("ACTP SEMANTIC PARTICIPANT H1 SUPPLEMENT")
    print("=" * 40)
    print()
    print("Model")
    print(f"  participants : {', '.join(report['model']['participants'])}")
    print(f"  channels     : {', '.join(report['model']['channels'])}")
    print(f"  interpretation: {report['model']['interpretation']}")
    print()
    print("Per-state results")
    print("  state        H1   expected   key asymmetry")
    for state_name, result in report["states"].items():
        print(
            f"  {state_name:12s} {result['h1']:2d}   {result['expected_h1']:2d}       "
            f"{result['key_asymmetry']}"
        )
    if report["mismatches"]:
        print()
        print("WARNING: expected values were not reproduced exactly.")
        for item in report["mismatches"]:
            print(f"  {item['state']}: expected {item['expected']}, got {item['actual']}")
    else:
        print()
        print("All expected Section 5 upper-bound values reproduced exactly.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute the ACTP conservative semantic participant H1 model.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
