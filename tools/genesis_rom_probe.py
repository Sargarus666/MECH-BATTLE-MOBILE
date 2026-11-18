#!/usr/bin/env python3
"""Read-only Sega Genesis ROM header and vector-table probe.

This deliberately does not disassemble instructions or claim full code discovery.
It never writes the ROM, extracts ZIP members to disk, or emits ROM-derived files.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

MAX_ROM_BYTES = 64 * 1024 * 1024
ROM_SUFFIXES = {".bin", ".gen", ".md", ".rom"}

VECTOR_NAMES = {
    2: "bus_error",
    3: "address_error",
    4: "illegal_instruction",
    5: "divide_by_zero",
    6: "chk",
    7: "trapv",
    8: "privilege_violation",
    9: "trace",
    10: "line_1010_emulator",
    11: "line_1111_emulator",
    24: "spurious_interrupt",
    25: "level_1_interrupt",
    26: "level_2_interrupt",
    27: "level_3_interrupt",
    28: "level_4_interrupt",
    29: "level_5_interrupt",
    30: "level_6_interrupt",
    31: "level_7_interrupt",
}
VECTOR_NAMES.update({32 + n: f"trap_{n}" for n in range(16)})


class ProbeError(ValueError):
    """Invalid or unsupported input image."""


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def _text(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="replace").strip()


def _computed_checksum(data: bytes) -> int:
    payload = data[0x200:]
    total = 0
    for offset in range(0, len(payload), 2):
        word = payload[offset] << 8
        if offset + 1 < len(payload):
            word |= payload[offset + 1]
        total = (total + word) & 0xFFFF
    return total


def read_rom_image(path: str | Path) -> tuple[bytes, str]:
    """Read a raw ROM or one unambiguous ROM member from a ZIP, in memory only."""
    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise ProbeError(f"cannot read input: {exc}") from exc

    if len(raw) > MAX_ROM_BYTES:
        raise ProbeError(f"input exceeds the {MAX_ROM_BYTES}-byte safety limit")

    if source.suffix.lower() == ".smd":
        raise ProbeError("interleaved .smd images are not supported yet; provide a verified linear .bin/.gen/.md/.rom image")

    if raw.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                candidates = [
                    item
                    for item in archive.infolist()
                    if not item.is_dir()
                    and Path(item.filename).suffix.lower() in ROM_SUFFIXES
                ]
                if len(candidates) != 1:
                    raise ProbeError(
                        f"ZIP must contain exactly one supported ROM image; found {len(candidates)}"
                    )
                item = candidates[0]
                if item.flag_bits & 0x1:
                    raise ProbeError("encrypted ZIP members are not supported")
                if item.file_size <= 0 or item.file_size > MAX_ROM_BYTES:
                    raise ProbeError("ZIP member is empty or exceeds the ROM safety limit")
                with archive.open(item, "r") as member:
                    data = member.read(MAX_ROM_BYTES + 1)
                if len(data) != item.file_size or len(data) > MAX_ROM_BYTES:
                    raise ProbeError("ZIP member size does not match its directory entry")
                return data, f"{source}!{item.filename}"
        except zipfile.BadZipFile as exc:
            raise ProbeError("input has a ZIP signature but is not a valid ZIP archive") from exc

    return raw, str(source)


def parse_rom(data: bytes, source: str = "<memory>") -> dict[str, Any]:
    if len(data) < 0x200:
        raise ProbeError(f"image is too small for a Genesis header ({len(data)} bytes)")
    if data[0x100:0x104] != b"SEGA":
        raise ProbeError("Genesis header signature 'SEGA' was not found at 0x100")

    initial_sp = _u32(data, 0x00)
    # The 68000 exposes a 24-bit physical address bus. Some ROMs encode
    # the initial stack pointer as a sign-extended 32-bit address (e.g.
    # 0xFFFFFFFC), which aliases the final longword of work RAM (0xFFFFFC).
    initial_sp_bus_address = initial_sp & 0x00FFFFFF
    initial_pc = _u32(data, 0x04)
    expected_checksum = _u16(data, 0x18E)
    computed_checksum = _computed_checksum(data)

    vector_entries: list[dict[str, Any]] = []
    entry_points: set[int] = set()
    if 0x200 <= initial_pc < len(data) and initial_pc % 2 == 0:
        entry_points.add(initial_pc)

    for vector_number, name in sorted(VECTOR_NAMES.items()):
        address = _u32(data, vector_number * 4)
        if address == 0:
            continue
        in_rom = 0x200 <= address < len(data)
        even = address % 2 == 0
        vector_entries.append(
            {
                "vector": vector_number,
                "name": name,
                "address": f"0x{address:08X}",
                "even": even,
                "in_rom": in_rom,
                "candidate_code_entry": bool(in_rom and even),
            }
        )
        if in_rom and even:
            entry_points.add(address)

    declared_start = _u32(data, 0x1A0)
    declared_end = _u32(data, 0x1A4)
    declared_size = declared_end - declared_start + 1 if declared_end >= declared_start else None

    return {
        "source": source,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header": {
            "console": _text(data[0x100:0x110]),
            "copyright": _text(data[0x110:0x120]),
            "title_domestic": _text(data[0x120:0x150]),
            "title_overseas": _text(data[0x150:0x180]),
            "serial": _text(data[0x180:0x18E]),
            "checksum_expected": f"0x{expected_checksum:04X}",
            "checksum_computed": f"0x{computed_checksum:04X}",
            "checksum_matches": expected_checksum == computed_checksum,
            "rom_start": f"0x{declared_start:08X}",
            "rom_end": f"0x{declared_end:08X}",
            "declared_size_bytes": declared_size,
            "region": _text(data[0x1F0:0x1F3]),
        },
        "initial_stack_pointer": f"0x{initial_sp:08X}",
        "initial_stack_pointer_bus_address": f"0x{initial_sp_bus_address:06X}",
        "initial_stack_pointer_in_work_ram": 0xFF0000 <= initial_sp_bus_address <= 0xFFFFFF and initial_sp_bus_address % 2 == 0,
        "reset_pc": f"0x{initial_pc:08X}",
        "reset_pc_valid_rom_target": 0x200 <= initial_pc < len(data) and initial_pc % 2 == 0,
        "m68k_vector_entries": vector_entries,
        "m68k_candidate_entry_points": [f"0x{x:08X}" for x in sorted(entry_points)],
        "m68k_discovery_status": "vector_seeds_only",
        "m68k_discovery_note": "The vector table supplies starting candidates only; it does not resolve branches, indirect dispatch, copied code, overlays, or self-modifying code.",
        "z80_discovery_status": "not_performed",
        "z80_discovery_note": "The cartridge header does not identify the sound-driver image. Trace 68000 upload/copy paths and Z80 RAM variants before making a Z80 compatibility claim.",
    }


def format_text(result: dict[str, Any]) -> str:
    header = result["header"]
    lines = [
        f"Source: {result['source']}",
        f"Size: {result['size_bytes']} bytes",
        f"SHA-256: {result['sha256']}",
        f"Title: {header['title_overseas'] or header['title_domestic'] or '(not set)'}",
        f"Serial: {header['serial'] or '(not set)'}",
        f"Region: {header['region'] or '(not set)'}",
        f"Reset SP: {result['initial_stack_pointer']} (24-bit bus: {result['initial_stack_pointer_bus_address']}, work RAM: {result['initial_stack_pointer_in_work_ram']})",
        f"Reset PC: {result['reset_pc']} (valid ROM target: {result['reset_pc_valid_rom_target']})",
        f"Checksum: expected {header['checksum_expected']}, computed {header['checksum_computed']} (match: {header['checksum_matches']})",
        "68000 vector entry candidates: " + ", ".join(result["m68k_candidate_entry_points"]),
        "68000 discovery: vector seeds only; no disassembly or dispatch resolution",
        "Z80 discovery: not performed",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="raw linear Genesis ROM or ZIP containing exactly one supported ROM image")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        data, source = read_rom_image(args.rom)
        result = parse_rom(data, source)
    except ProbeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
