#!/usr/bin/env python3
"""
H¹ Protocol Linter
===================
CLI tool for computing sheaf cohomology H¹ on protocol state machines.

Usage:
    python3 h1_lint.py                            # Default ACTP protocol
    python3 h1_lint.py --config my_protocol.yaml  # Custom protocol
    python3 h1_lint.py --2complex                 # Include explicit 2-complex analysis
    python3 h1_lint.py --diff v1.yaml v2.yaml     # Compare two versions
    python3 h1_lint.py --json                     # JSON output (for CI)
    python3 h1_lint.py --leaks                    # Show dimension leak details
    python3 h1_lint.py --leaks --path dispute     # Leaks for specific path
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

# Import engine from same directory
sys.path.insert(0, str(Path(__file__).parent))
from h1_engine import (
    analyse_protocol, analyse_protocol_2complex, analyse_path, trace_leaks,
    validate_protocol, field_loss, ProtocolValidationError,
)


def _validate_path_sequence(edges: list, transitions_by_name: dict, face_name: str, side: str) -> tuple:
    """Validate that a list of named transitions forms a directed path."""
    if not edges:
        print(f"ERROR: Face '{face_name}' has empty '{side}' path", file=sys.stderr)
        sys.exit(1)

    first = transitions_by_name[edges[0]]
    start = first["from"]
    current = first["to"]

    for edge in edges[1:]:
        transition = transitions_by_name[edge]
        if transition["from"] != current:
            print(
                f"ERROR: Face '{face_name}' has non-contiguous '{side}' path at edge '{edge}' "
                f"(expected source '{current}', got '{transition['from']}')",
                file=sys.stderr,
            )
            sys.exit(1)
        current = transition["to"]

    return start, current


def load_protocol(config_path: str) -> dict:
    """Load and validate a protocol YAML file."""
    with open(config_path, "r") as f:
        proto = yaml.safe_load(f)

    if "states" not in proto:
        print(f"ERROR: {config_path} missing 'states' section", file=sys.stderr)
        sys.exit(1)
    if "transitions" not in proto:
        print(f"ERROR: {config_path} missing 'transitions' section", file=sys.stderr)
        sys.exit(1)

    states = {}
    for name, defn in proto["states"].items():
        if isinstance(defn, dict) and "stalks" in defn:
            states[name] = defn["stalks"]
        elif isinstance(defn, list):
            states[name] = defn
        else:
            print(f"ERROR: State '{name}' has no stalks defined", file=sys.stderr)
            sys.exit(1)

    transitions = proto["transitions"]
    transition_names = set()
    for t in transitions:
        if t["from"] not in states:
            print(f"ERROR: Transition '{t['name']}' references unknown state '{t['from']}'", file=sys.stderr)
            sys.exit(1)
        if t["to"] not in states:
            print(f"ERROR: Transition '{t['name']}' references unknown state '{t['to']}'", file=sys.stderr)
            sys.exit(1)
        if t["name"] in transition_names:
            print(f"ERROR: Duplicate transition name '{t['name']}'", file=sys.stderr)
            sys.exit(1)
        transition_names.add(t["name"])

    paths = proto.get("paths", {})
    for pname, pdef in paths.items():
        for s in pdef.get("states", []):
            if s not in states:
                print(f"ERROR: Path '{pname}' references unknown state '{s}'", file=sys.stderr)
                sys.exit(1)

    faces = proto.get("faces", [])
    transitions_by_name = {t["name"]: t for t in transitions}
    for face in faces:
        face_name = face.get("name")
        if not face_name:
            print("ERROR: Face missing 'name'", file=sys.stderr)
            sys.exit(1)

        plus = face.get("plus")
        minus = face.get("minus")
        if not isinstance(plus, list) or not isinstance(minus, list):
            print(f"ERROR: Face '{face_name}' must define list-valued 'plus' and 'minus' paths", file=sys.stderr)
            sys.exit(1)

        for edge in plus + minus:
            if edge not in transitions_by_name:
                print(f"ERROR: Face '{face_name}' references unknown transition '{edge}'", file=sys.stderr)
                sys.exit(1)

        plus_start, plus_end = _validate_path_sequence(plus, transitions_by_name, face_name, "plus")
        minus_start, minus_end = _validate_path_sequence(minus, transitions_by_name, face_name, "minus")
        if plus_start != minus_start or plus_end != minus_end:
            print(
                f"ERROR: Face '{face_name}' has mismatched endpoints "
                f"({plus_start}->{plus_end} vs {minus_start}->{minus_end})",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        validate_protocol(states, transitions, faces)
    except ProtocolValidationError as exc:
        print(f"ERROR: {config_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    return {
        "name": proto.get("name", "Unknown"),
        "version": proto.get("version", "?"),
        "states": states,
        "transitions": transitions,
        "paths": paths,
        "faces": faces,
    }


def status_icon(h1: int, expect: int = None) -> str:
    """Return status icon for an H¹ value."""
    if h1 == 0:
        return "✅"
    if expect is not None and h1 <= expect:
        return "🟡"
    return "⚠️"


def build_report(proto: dict, include_two_complex: bool = False) -> dict:
    """Collect full, path, leak, and optional 2-complex diagnostics."""
    states = proto["states"]
    transitions = proto["transitions"]
    paths = proto.get("paths", {})
    faces = proto.get("faces", [])

    full = analyse_protocol(states, transitions)
    report = {
        "protocol": f"{proto['name']} v{proto['version']}",
        "full": {
            "h0": full["dim_h0"],
            "h1": full["dim_h1"],
            "c0": full["dim_c0"],
            "c1": full["dim_c1"],
            "rank_delta0": full["rank_delta0"],
            "status": "pass" if full["dim_h1"] == 0 else "warn",
        },
        "paths": {},
        "leaks": trace_leaks(states, transitions),
        "field_loss": field_loss(states, transitions),
        "regressions": [],
    }

    if include_two_complex and faces:
        two = analyse_protocol_2complex(states, transitions, faces)
        report["two_complex"] = {
            "h0": two["dim_h0"],
            "h1": two["dim_h1"],
            "h2": two["dim_h2"],
            "c0": two["dim_c0"],
            "c1": two["dim_c1"],
            "c2": two["dim_c2"],
            "rank_delta0": two["rank_delta0"],
            "rank_delta1": two["rank_delta1"],
            "ker_delta1": two["dim_ker_delta1"],
            "complex_residual": two["complex_residual"],
            "faces": two["faces"],
            "status": "pass" if two["dim_h1"] == 0 else "warn",
        }

    for pname, pdef in paths.items():
        path_states = pdef.get("states", [])
        result = analyse_path(states, transitions, path_states)
        expect = pdef.get("expect_h1")

        status = "pass" if result["dim_h1"] == 0 else "warn"
        if expect is not None and result["dim_h1"] != expect:
            status = "fail"
            report["regressions"].append({
                "path": pname,
                "expected": expect,
                "actual": result["dim_h1"],
            })

        report["paths"][pname] = {
            "h1": result["dim_h1"],
            "h0": result["dim_h0"],
            "c0": result["dim_c0"],
            "c1": result["dim_c1"],
            "rank_delta0": result["rank_delta0"],
            "status": status,
            "description": pdef.get("description", ""),
            "expect_h1": expect,
            "expect_h1_info": pdef.get("expect_h1_info", ""),
        }

    if report["regressions"]:
        report["verdict"] = "fail"
    elif include_two_complex and "two_complex" in report and report["two_complex"]["h1"] == 0:
        report["verdict"] = "pass"
    elif full["dim_h1"] == 0:
        report["verdict"] = "pass"
    else:
        report["verdict"] = "warn"

    return report


def print_human(proto: dict, report: dict, show_leaks: bool = False, leak_path: str = None, show_2complex: bool = False):
    """Human-readable output."""
    states = proto["states"]
    paths = proto.get("paths", {})
    faces = proto.get("faces", [])
    full = report["full"]

    print()
    print(f"H¹ PROTOCOL LINTER — {report['protocol']}")
    print("═" * 50)
    print()

    print("STATES")
    for sname in sorted(states.keys()):
        dims = states[sname]
        print(f"  {sname:15s}  dim = {len(dims):2d}")
    print()

    print("FULL PROTOCOL (1-COMPLEX)")
    icon = status_icon(full["h1"])
    h1_desc = "topologically complete" if full["h1"] == 0 else f"{full['h1']} obstructions"
    print(f"  H¹ = {full['h1']:3d}  {icon}  {h1_desc}")
    print(f"  H⁰ = {full['h0']:3d}  (global sections)")
    print(f"  C⁰ = {full['c0']:3d}  C¹ = {full['c1']:3d}  rank(δ₀) = {full['rank_delta0']}")
    print()
    print("  Note: H¹ counts cycles in each field's support graph, not lost data.")
    print()

    fl = report.get("field_loss")
    if fl is not None:
        print("FIELD LOSS (direct score: dropped + missing invariant fields)")
        print(f"  score = {fl['score']}  invariant fields = {len(fl['invariant_fields'])}")
        for d in fl["dropped"]:
            print(f"    dropped  {d['field']:22s} at {d['transition']} ({d['from']} → {d['to']})")
        for m in fl["missing"]:
            print(f"    missing  {m['field']:22s} at {m['state']}")
        if fl["declared_drops"]:
            print(f"  ({len(fl['declared_drops'])} declared intentional drops not scored)")
        print()

    if show_2complex:
        if "two_complex" not in report:
            print("FULL PROTOCOL (2-COMPLEX)")
            if faces:
                print("  Unable to compute 2-complex report.")
            else:
                print("  No faces defined in YAML; add a 'faces:' section first.")
            print()
        else:
            two = report["two_complex"]
            icon = status_icon(two["h1"])
            h1_desc = "topologically complete" if two["h1"] == 0 else f"{two['h1']} obstructions"
            print("FULL PROTOCOL (2-COMPLEX)")
            print(f"  H¹ = {two['h1']:3d}  {icon}  {h1_desc}")
            print(f"  H² = {two['h2']:3d}  (higher-order face classes)")
            print(f"  C⁰ = {two['c0']:3d}  C¹ = {two['c1']:3d}  C² = {two['c2']:3d}")
            print(f"  rank(δ₀) = {two['rank_delta0']:2d}  rank(δ₁) = {two['rank_delta1']:2d}  dim ker(δ₁) = {two['ker_delta1']:2d}")
            print(f"  faces = {len(two['faces']):2d}  max|δ₁δ₀| = {two['complex_residual']:.1e}")
            print()

    if paths:
        print("PATHS")
        for pname, pdef in paths.items():
            result = report["paths"][pname]
            icon = status_icon(result["h1"], result.get("expect_h1"))
            info = result.get("expect_h1_info", "")
            expect = result.get("expect_h1")
            suffix = ""
            if result["h1"] == 0:
                suffix = "topologically complete"
            elif info:
                suffix = info
            elif expect is not None and result["h1"] != expect:
                suffix = f"REGRESSION — expected {expect}"
            else:
                suffix = f"{result['h1']} obstructions"

            print(f"  {icon} {pname:18s} H¹ = {result['h1']:<3d} — {suffix}")
            if result.get("description"):
                print(f"     {result['description']}")
        print()

    if report["regressions"]:
        print("🔴 REGRESSIONS DETECTED")
        for regression in report["regressions"]:
            print(
                f"  {regression['path']}: expected H¹ = {regression['expected']}, "
                f"got H¹ = {regression['actual']}"
            )
        print()

    if show_leaks:
        path_filter = None
        if leak_path and leak_path in paths:
            path_filter = paths[leak_path].get("states")
            print(f"DIMENSION LEAKS ({leak_path} path)")
        else:
            print("DIMENSION LEAKS (all transitions)")

        leaks = trace_leaks(proto["states"], proto["transitions"], path_filter)
        if not leaks:
            print("  No dimension leaks detected.")
        else:
            for leak in leaks:
                print(f"  {leak['from']} → {leak['to']} ({leak['name']})")
                print(f"    shared: {leak['shared_count']}/{leak['source_total']} dims")
                if leak["lost_from_source"]:
                    print(f"    LOST:   {', '.join(leak['lost_from_source'])}")
                if leak["gained_at_target"]:
                    print(f"    NEW:    {', '.join(leak['gained_at_target'])}")
                print()

    print("─" * 50)
    if show_2complex and "two_complex" in report:
        print(f"VERDICT: 1-complex H¹ = {full['h1']} (diagnostic), 2-complex H¹ = {report['two_complex']['h1']} (topological completeness).")
    elif full["h1"] == 0:
        print("VERDICT: ✅ Protocol is topologically complete on the 1-complex. H¹ = 0.")
    else:
        print(f"VERDICT: ⚠️  1-complex H¹ = {full['h1']} — structural obstructions exist.")
        print("  Use --2complex to test an explicit face refinement, or --leaks to inspect edge-level losses.")

    if report["regressions"]:
        print("EXIT CODE: 1 (named path regression)")
    print()


def print_json(report: dict):
    """JSON output for CI integration."""
    print(json.dumps(report, indent=2))


def print_diff(proto_a: dict, proto_b: dict, include_two_complex: bool = False) -> int:
    """Compare two protocol versions."""
    report_a = build_report(proto_a, include_two_complex=include_two_complex)
    report_b = build_report(proto_b, include_two_complex=include_two_complex)

    name_a = report_a["protocol"]
    name_b = report_b["protocol"]

    print()
    print(f"H¹ DIFF: {name_a} → {name_b}")
    print("═" * 50)
    print()

    delta = report_b["full"]["h1"] - report_a["full"]["h1"]
    if delta < 0:
        icon = "✅"
        delta_str = f"({delta} obstructions)"
    elif delta == 0:
        icon = "—"
        delta_str = "(unchanged)"
    else:
        icon = "🔴"
        delta_str = f"(+{delta} obstructions!)"
    print(f"  Full 1-complex: H¹ {report_a['full']['h1']:3d} → {report_b['full']['h1']:3d}  {icon} {delta_str}")

    if include_two_complex and "two_complex" in report_a and "two_complex" in report_b:
        delta = report_b["two_complex"]["h1"] - report_a["two_complex"]["h1"]
        if delta < 0:
            icon = "✅"
            delta_str = f"({delta})"
        elif delta == 0:
            icon = "—"
            delta_str = "(unchanged)"
        else:
            icon = "🔴"
            delta_str = f"(+{delta}!)"
        print(f"  Full 2-complex: H¹ {report_a['two_complex']['h1']:3d} → {report_b['two_complex']['h1']:3d}  {icon} {delta_str}")

    all_paths = set(proto_a.get("paths", {}).keys()) | set(proto_b.get("paths", {}).keys())
    for pname in sorted(all_paths):
        if pname in report_a["paths"] and pname in report_b["paths"]:
            res_a = report_a["paths"][pname]
            res_b = report_b["paths"][pname]
            delta = res_b["h1"] - res_a["h1"]
            if delta < 0:
                icon = "✅"
                delta_str = "RESOLVED ✨" if res_b["h1"] == 0 else f"({delta})"
            elif delta == 0:
                icon = "—"
                delta_str = "(unchanged)"
            else:
                icon = "🔴"
                delta_str = f"(+{delta}!)"
            print(f"  {pname:18s} H¹ {res_a['h1']:3d} → {res_b['h1']:3d}  {icon} {delta_str}")
        elif pname in report_b["paths"]:
            print(f"  {pname:18s} NEW  H¹ = {report_b['paths'][pname]['h1']}")
        else:
            print(f"  {pname:18s} REMOVED")

    print()
    new_states = set(proto_b["states"].keys()) - set(proto_a["states"].keys())
    removed_states = set(proto_a["states"].keys()) - set(proto_b["states"].keys())
    if new_states:
        print("  New states:", ", ".join(sorted(new_states)))
    if removed_states:
        print("  Removed states:", ", ".join(sorted(removed_states)))

    changed = []
    for state_name in sorted(set(proto_a["states"].keys()) & set(proto_b["states"].keys())):
        a_dims = set(proto_a["states"][state_name])
        b_dims = set(proto_b["states"][state_name])
        added = b_dims - a_dims
        removed = a_dims - b_dims
        if added or removed:
            changed.append((state_name, added, removed))

    if changed:
        print()
        print("  Stalk changes:")
        for state_name, added, removed in changed:
            if added:
                print(f"    {state_name}: +{', '.join(sorted(added))}")
            if removed:
                print(f"    {state_name}: -{', '.join(sorted(removed))}")

    print()
    return 1 if report_b["regressions"] else 0


def main():
    parser = argparse.ArgumentParser(
        description="H¹ Protocol Linter — Sheaf cohomology for state machine verification"
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to protocol YAML (default: protocol.yaml in script directory)"
    )
    parser.add_argument(
        "--diff", "-d",
        nargs=2,
        metavar=("V1", "V2"),
        help="Compare two protocol versions"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output JSON (for CI integration)"
    )
    parser.add_argument(
        "--leaks", "-l",
        action="store_true",
        help="Show dimension leak details"
    )
    parser.add_argument(
        "--path", "-p",
        default=None,
        help="Filter leaks to a specific named path"
    )
    parser.add_argument(
        "--2complex",
        dest="two_complex",
        action="store_true",
        help="Compute explicit 2-complex cohomology when faces are defined in YAML"
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    default_config = script_dir / "protocol.yaml"

    if args.diff:
        proto_a = load_protocol(args.diff[0])
        proto_b = load_protocol(args.diff[1])
        sys.exit(print_diff(proto_a, proto_b, include_two_complex=args.two_complex))

    config_path = args.config or str(default_config)
    if not os.path.exists(config_path):
        print(f"ERROR: Config not found: {config_path}", file=sys.stderr)
        print(f"Create one or use: python3 h1_lint.py --config <path>", file=sys.stderr)
        sys.exit(1)

    proto = load_protocol(config_path)
    report = build_report(proto, include_two_complex=args.two_complex)

    if args.json:
        print_json(report)
    else:
        print_human(proto, report, show_leaks=args.leaks, leak_path=args.path, show_2complex=args.two_complex)

    sys.exit(1 if report["regressions"] else 0)


if __name__ == "__main__":
    main()
