#!/usr/bin/env python3
"""Run a private, read-only audit of a Genesis ROM with the segarecomp CLI.

The report contains only image identity/header metadata and aggregate discovery
counts. Temporary ROM copies and full reachability reports are kept in a
temporary directory and removed automatically. Generated C is optional and
must be written outside this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .genesis_rom_probe import ProbeError, parse_rom, read_rom_image
except ImportError:  # direct script execution from tools/
    from genesis_rom_probe import ProbeError, parse_rom, read_rom_image


class AuditError(RuntimeError):
    """The CLI or input did not produce a usable audit result."""


def _run(cli: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(cli), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AuditError(f"segarecomp {' '.join(args[:1])} timed out after {timeout}s") from exc
    except OSError as exc:
        raise AuditError(f"cannot execute segarecomp: {exc}") from exc


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout.strip() or result.stderr.strip()


def _json_output(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    output = _combined_output(result)
    start = output.find("{")
    if start < 0:
        raise AuditError(f"{name} did not return JSON (exit {result.returncode})")
    try:
        value, _ = json.JSONDecoder().raw_decode(output[start:])
    except json.JSONDecodeError as exc:
        raise AuditError(f"{name} returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"{name} returned a non-object JSON value")
    return value


def _require_success(name: str, result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        detail = _combined_output(result).splitlines()[:3]
        raise AuditError(f"{name} failed with exit {result.returncode}: {' | '.join(detail)}")


def _parse_inspect(output: str) -> dict[str, Any]:
    def field(name: str) -> str | None:
        match = re.search(rf"(?m)^{re.escape(name)}:\s*(\S+)\s*$", output)
        return match.group(1) if match else None

    return {
        "outcome": field("outcome"),
        "family": field("family"),
        "diagnostic": field("diagnostic"),
    }


def _parse_z80_report(output: str) -> dict[str, Any]:
    values = {key: int(value) for key, value in re.findall(r"([a-z][a-z0-9_.]*)=(\d+)", output)}
    outcome = re.search(r"\boutcome=([a-z_]+)", output)
    return {
        "outcome": outcome.group(1) if outcome else None,
        "epochs": values.get("epochs"),
        "candidates": values.get("candidates"),
        "steps": values.get("steps"),
        "nodes": values.get("nodes"),
        "contexts": values.get("contexts"),
        "copy_loops": values.get("copy_loops"),
        "decoder_calls": values.get("decoder_calls"),
        "staged_decodes": values.get("staged_decodes"),
        "horizon_paths": values.get("horizon_paths"),
        "images": values.get("images"),
        "refusals": {
            key.removeprefix("refusal."): value
            for key, value in values.items()
            if key.startswith("refusal.")
        },
    }


def _safe_reachability(report_path: Path) -> dict[str, Any]:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read private reachability report: {exc}") from exc

    aggregate = report.get("aggregate", {})
    sites = aggregate.get("sites", {})
    recovery = aggregate.get("pc_index_recovery", {})
    unknown_origins = recovery.get("index_unknown_origins", {})
    return {
        "discovered_instruction_starts": aggregate.get("discovered"),
        "call_continuations": aggregate.get("call_continuations"),
        "indirect_jsr_sites": sites.get("jsr_(An)"),
        "indexed_pc_jump_sites": sites.get("jmp_(d8,PC,Xn)"),
        "unmapped_target_count": aggregate.get("unmapped_targets"),
        "rejected_decode_target_count": aggregate.get("rejected_decode_targets"),
        "odd_target_count": aggregate.get("odd_targets"),
        "pc_index_recovery": {
            "sites_encountered": recovery.get("sites_encountered"),
            "resolved": recovery.get("resolved"),
            "unresolved": recovery.get("unresolved"),
            "index_unknown": recovery.get("outcomes", {}).get("index_unknown"),
            "unknown_origins": {key: value for key, value in unknown_origins.items() if value},
        },
    }



def _safe_decode_token_report(token_path: Path, reachability_path: Path, image_size: int) -> dict[str, Any]:
    """Cross-check reachable instruction starts against segarecomp's address-free token export."""
    try:
        data = token_path.read_bytes()
        reachability = json.loads(reachability_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read private decode-token evidence: {exc}") from exc

    header, separator, payload = data.partition(b"\n")
    match = re.fullmatch(
        rb"segarecomp\.m68k_decode_tokens\.v1 positions ([0-9]+) fields status length family control ea_src ea_dst width flags",
        header,
    )
    if not separator or match is None:
        raise AuditError("m68k-decode-token-report has an unknown header")
    positions = int(match.group(1))
    if positions != image_size // 2:
        raise AuditError("m68k-decode-token-report position count does not match the ROM image")
    if len(payload) != positions * 8 + 4 or not payload.endswith(b"end\n"):
        raise AuditError("m68k-decode-token-report has an invalid body length or trailer")
    tokens = payload[:-4]

    discovered = reachability.get("discovered")
    aggregate = reachability.get("aggregate", {})
    if not isinstance(discovered, list) or aggregate.get("discovered") != len(discovered):
        raise AuditError("reachability instruction-start list does not match its aggregate count")

    status_counts: Counter[int] = Counter()
    family_counts: Counter[int] = Counter()
    control_counts: Counter[int] = Counter()
    for address in discovered:
        if not isinstance(address, str) or re.fullmatch(r"(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})", address) is None:
            raise AuditError("reachability contains an invalid instruction-start address")
        pc = int(address, 16)
        if pc & 1 or pc >= image_size:
            raise AuditError("reachability instruction start is odd or outside the ROM image")
        row = tokens[(pc // 2) * 8 : (pc // 2 + 1) * 8]
        status, length, family, control, ea_src, ea_dst, width, flags = row
        if status > 2 or length > 5 or family > 7 or control > 7 or ea_src > 12 or ea_dst > 12 or width > 3 or flags > 3:
            raise AuditError("m68k-decode-token-report contains an out-of-range field")
        if status == 0 and any(row):
            raise AuditError("rejected decode-token row is not zero-filled")
        status_counts[status] += 1
        if status == 2:
            family_counts[family] += 1
            control_counts[control] += 1

    family_names = {1: "move", 2: "arithmetic", 3: "logic_bit", 4: "shift", 5: "control", 6: "exception_raising", 7: "other"}
    control_names = {0: "none", 1: "conditional", 2: "direct_jump", 3: "direct_call", 4: "dynamic_jump", 5: "dynamic_call", 6: "return", 7: "always_exception_or_trap"}
    sites = aggregate.get("sites", {})
    dynamic_call_site_count = sum(sites.get(name, 0) for name in ("jsr_(An)", "jsr_d16(An)", "jsr_(d8,An,Xn)", "jsr_(d8,PC,Xn)"))
    dynamic_jump_site_count = sum(sites.get(name, 0) for name in ("jmp_(An)", "jmp_d16(An)", "jmp_(d8,An,Xn)", "jmp_(d8,PC,Xn)"))
    dynamic_calls = control_counts[5]
    dynamic_jumps = control_counts[4]
    return {
        "discovered_instruction_starts": len(discovered),
        "status_counts": {
            "ordinary": status_counts[2],
            "architectural_exception": status_counts[1],
            "rejected_or_undecodable": status_counts[0],
        },
        "ordinary_family_counts": {family_names[key]: value for key, value in sorted(family_counts.items())},
        "ordinary_control_counts": {control_names[key]: value for key, value in sorted(control_counts.items())},
        "dynamic_calls": dynamic_calls,
        "dynamic_jumps": dynamic_jumps,
        "dynamic_call_count_matches_reachability": dynamic_calls == dynamic_call_site_count,
        "dynamic_jump_count_matches_reachability": dynamic_jumps == dynamic_jump_site_count,
    }


def _outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repository = Path(__file__).resolve().parents[1]
    if resolved == repository or repository in resolved.parents:
        raise AuditError("ROM-specific outputs must be stored outside the Git repository")
    return resolved


def run_audit(
    cli_path: str | Path,
    rom_path: str | Path,
    *,
    timeout: int = 600,
    generated_c_path: str | Path | None = None,
) -> dict[str, Any]:
    if timeout <= 0:
        raise AuditError("timeout must be a positive number of seconds")
    cli = Path(cli_path).expanduser().resolve()
    if not cli.is_file():
        raise AuditError(f"segarecomp CLI not found: {cli}")

    try:
        rom_bytes, _source = read_rom_image(rom_path)
        header = parse_rom(rom_bytes)
    except ProbeError as exc:
        raise AuditError(str(exc)) from exc

    rom_sha256 = hashlib.sha256(rom_bytes).hexdigest()
    report: dict[str, Any] = {
        "schema": "mech-battle.segarecomp-rom-audit.v1",
        "rom": {
            "size_bytes": len(rom_bytes),
            "sha256": rom_sha256,
            "checksum_expected": header["header"]["checksum_expected"],
            "checksum_computed": header["header"]["checksum_computed"],
            "checksum_matches": header["header"]["checksum_matches"],
            "region": header["header"]["region"],
            "reset_pc_valid": header["reset_pc_valid_rom_target"],
            "initial_stack_pointer_in_work_ram": header["initial_stack_pointer_in_work_ram"],
        },
    }

    with tempfile.TemporaryDirectory(prefix="segarecomp-rom-audit-") as temporary:
        private = Path(temporary)
        private_rom = private / "input.gen"
        private_rom.write_bytes(rom_bytes)

        inspected = _run(cli, ["inspect", str(private_rom)], timeout)
        _require_success("inspect", inspected)
        report["inspect"] = _parse_inspect(_combined_output(inspected))
        if report["inspect"]["family"] != "genesis":
            raise AuditError("the supplied image was not recognized as a Genesis ROM")

        analyzed = _run(cli, ["analyze", str(private_rom)], timeout)
        _require_success("analyze", analyzed)
        analysis = _json_output("analyze", analyzed)
        if analysis.get("outcome") != "accepted":
            raise AuditError(f"reset image analysis was not accepted: {analysis.get('diagnostic', 'unknown')}")
        raw_region = analysis.get("raw_region", {})
        image_range = raw_region.get("image_range", [None, None])
        mapped_bytes = (
            image_range[1] - image_range[0]
            if len(image_range) == 2 and all(isinstance(value, int) for value in image_range)
            else None
        )
        report["reset_analysis"] = {
            "outcome": analysis.get("outcome"),
            "diagnostic": analysis.get("diagnostic"),
            "entry_point_valid": analysis.get("entry_image_offset") is not None,
            "mapping": raw_region.get("mapping"),
            "mapped_bytes": mapped_bytes,
        }

        startup = _run(cli, ["genesis-general-startup", str(private_rom)], timeout)
        startup_json = _json_output("genesis-general-startup", startup)
        frontiers = startup_json.get("frontiers", [])
        report["m68k_startup"] = {
            "result": startup_json.get("result"),
            "completed_blocks": startup_json.get("completed_blocks"),
            "frontier_count": len(frontiers),
            "frontier_categories": dict(Counter(item.get("category", "unknown") for item in frontiers)),
            "frontier_classes": dict(Counter(item.get("class", "unknown") for item in frontiers)),
        }

        private_reachability = private / "reachability.json"
        reachability = _run(
            cli,
            [
                "genesis-reachability-challenger",
                "--rom", str(private_rom),
                "--reset-entry",
                "--rom-sha256", rom_sha256,
                "--private-output", str(private_reachability),
                "--pc-index-recovery",
                "--pc-index-width-domains",
            ],
            timeout,
        )
        _require_success("genesis-reachability-challenger", reachability)
        report["m68k_reachability"] = _safe_reachability(private_reachability)

        private_tokens = private / "m68k-decode-tokens.bin"
        token_report = _run(
            cli,
            ["m68k-decode-token-report", "--rom", str(private_rom), "--output", str(private_tokens)],
            timeout,
        )
        _require_success("m68k-decode-token-report", token_report)
        report["m68k_decode_tokens"] = _safe_decode_token_report(private_tokens, private_reachability, len(rom_bytes))

        z80 = _run(cli, ["genesis-z80-static-report", "--rom", str(private_rom)], timeout)
        _require_success("genesis-z80-static-report", z80)
        report["z80_static"] = _parse_z80_report(_combined_output(z80))

        if generated_c_path is not None:
            output_c = _outside_repository(Path(generated_c_path))
            output_c.parent.mkdir(parents=True, exist_ok=True)
            emitted = _run(
                cli,
                [
                    "emit-general-startup-bridge-c",
                    "--rom", str(private_rom),
                    "--reset-entry",
                    "--rom-sha256", rom_sha256,
                    "--generated-c-output", str(output_c),
                ],
                timeout,
            )
            _require_success("emit-general-startup-bridge-c", emitted)
            if not output_c.is_file() or output_c.stat().st_size == 0:
                raise AuditError("the recompiler reported success but generated C is missing or empty")
            report["generated_c"] = {
                "emitted": True,
                "size_bytes": output_c.stat().st_size,
                "stored_outside_repository": True,
            }
        else:
            report["generated_c"] = {"emitted": False}

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="linear Genesis ROM or ZIP containing exactly one supported image")
    parser.add_argument("--cli", required=True, help="path to a built segarecomp CLI executable")
    parser.add_argument("--timeout", type=int, default=600, help="per-command timeout in seconds (default: 600)")
    parser.add_argument("--emit-c", metavar="PATH", help="optionally emit private generated C to PATH outside this repository")
    parser.add_argument("--report", metavar="PATH", help="write the aggregate JSON report outside this repository")
    args = parser.parse_args(argv)

    try:
        report = run_audit(args.cli, args.rom, timeout=args.timeout, generated_c_path=args.emit_c)
        rendered = json.dumps(report, indent=2, ensure_ascii=False)
        if args.report:
            destination = _outside_repository(Path(args.report))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
    except (AuditError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
