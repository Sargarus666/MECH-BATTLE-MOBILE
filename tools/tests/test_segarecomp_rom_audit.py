import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.segarecomp_rom_audit import AuditError, run_audit


def make_rom() -> bytes:
    data = bytearray(0x400)
    data[0:4] = struct.pack(">I", 0xFFFFFFFC)
    data[4:8] = struct.pack(">I", 0x00000200)
    data[8:12] = struct.pack(">I", 0x00000220)
    data[0x100:0x110] = b"SEGA GENESIS    "
    data[0x120:0x150] = b"TEST FIXTURE".ljust(48, b" ")
    data[0x150:0x180] = b"TEST FIXTURE".ljust(48, b" ")
    data[0x180:0x18E] = b"GM 00000000-00"
    data[0x1A0:0x1A4] = struct.pack(">I", 0)
    data[0x1A4:0x1A8] = struct.pack(">I", len(data) - 1)
    data[0x1F0:0x1F3] = b"U  "
    data[0x200:0x204] = b"\x70\x00\x4E\x75"
    checksum = sum(int.from_bytes(data[offset:offset + 2], "big")
                   for offset in range(0x200, len(data), 2)) & 0xFFFF
    data[0x18E:0x190] = struct.pack(">H", checksum)
    return bytes(data)


FAKE_CLI = r'''#!/bin/sh
command="$1"
shift
case "$command" in
  inspect)
    printf '%s\n' 'outcome: recognized' 'diagnostic: HDR_RECOGNIZED_GENESIS' 'family: genesis'
    ;;
  analyze)
    printf '%s\n' '{"outcome":"accepted","diagnostic":"GENESIS_RESET_IMAGE_ACCEPTED","entry_image_offset":512,"raw_region":{"mapping":"identity_non_mirrored","image_range":[0,1024]}}'
    ;;
  genesis-general-startup)
    printf '%s\n' '{"result":"partial","completed_blocks":12,"frontiers":[{"category":"unmapped_data_access","class":"GENESIS_STOP_UNSUPPORTED_MEMORY_REGION","address":"SECRET"},{"category":"discovery_budget_exhausted","class":"GENESIS_STOP_DISCOVERY_PREFIX_BOUNDARY","address":"SECRET"}]}'
    exit 1
    ;;
  genesis-reachability-challenger)
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "--private-output" ]; then shift; report="$1"; fi
      shift
    done
    cat > "$report" <<'JSON'
{"aggregate":{"discovered":77,"call_continuations":9,"unmapped_targets":2,"rejected_decode_targets":0,"odd_targets":0,"sites":{"jsr_(An)":3,"jmp_(d8,PC,Xn)":1},"pc_index_recovery":{"sites_encountered":1,"resolved":0,"unresolved":1,"outcomes":{"index_unknown":1},"index_unknown_origins":{"untracked_load_or_source":1}}},"discovered":["SECRET_ADDRESS"],"unmapped_targets":["SECRET_TARGET"]}
JSON
    printf '%s\n' '{"outcome":"partial"}'
    ;;
  genesis-z80-static-report)
    printf '%s\n' 'outcome=partial epochs=2 candidates=2 steps=30 nodes=12 contexts=5 copy_loops=1 decoder_calls=0 staged_decodes=0 horizon_paths=3 images=1 refusal.length_unknown=1'
    ;;
  emit-general-startup-bridge-c)
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "--generated-c-output" ]; then shift; generated="$1"; fi
      shift
    done
    printf '%s\n' '/* generated privately */' > "$generated"
    ;;
  *)
    echo 'unknown command' >&2
    exit 2
    ;;
esac
'''


class SegarecompRomAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.rom = self.directory / "fixture.gen"
        self.rom.write_bytes(make_rom())
        self.cli = self.directory / "fake-segarecomp"
        self.cli.write_text(FAKE_CLI, encoding="utf-8")
        self.cli.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def test_aggregates_private_discovery_without_leaking_addresses(self):
        report = run_audit(self.cli, self.rom)
        self.assertEqual(report["inspect"]["family"], "genesis")
        self.assertEqual(report["reset_analysis"]["outcome"], "accepted")
        self.assertEqual(report["m68k_startup"]["result"], "partial")
        self.assertEqual(report["m68k_startup"]["completed_blocks"], 12)
        self.assertEqual(report["m68k_startup"]["frontier_count"], 2)
        self.assertEqual(report["m68k_reachability"]["discovered_instruction_starts"], 77)
        self.assertEqual(report["m68k_reachability"]["indirect_jsr_sites"], 3)
        self.assertEqual(report["m68k_reachability"]["pc_index_recovery"]["index_unknown"], 1)
        self.assertEqual(report["z80_static"]["refusals"]["length_unknown"], 1)
        serialized = json.dumps(report)
        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("SECRET_ADDRESS", serialized)
        self.assertNotIn("SECRET_TARGET", serialized)

    def test_can_read_a_single_rom_from_zip_without_persisting_it(self):
        archive = self.directory / "fixture.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("private/fixture.gen", make_rom())
        report = run_audit(self.cli, archive)
        self.assertEqual(report["rom"]["size_bytes"], 0x400)
        self.assertEqual(report["inspect"]["outcome"], "recognized")

    def test_generated_c_must_be_outside_repository(self):
        repository_output = Path(__file__).resolve().parents[2] / "should-not-exist.c"
        with self.assertRaises(AuditError):
            run_audit(self.cli, self.rom, generated_c_path=repository_output)

    def test_optional_generated_c_is_emitted_outside_repository(self):
        generated = self.directory / "generated.c"
        report = run_audit(self.cli, self.rom, generated_c_path=generated)
        self.assertEqual(report["generated_c"]["emitted"], True)
        self.assertEqual(report["generated_c"]["size_bytes"], len(b"/* generated privately */\n"))
        self.assertTrue(generated.is_file())


if __name__ == "__main__":
    unittest.main()
