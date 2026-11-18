import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.genesis_rom_probe import ProbeError, parse_rom, read_rom_image


def make_rom() -> bytes:
    data = bytearray(0x400)
    data[0:4] = struct.pack(">I", 0x00FFFFFC)
    data[4:8] = struct.pack(">I", 0x00000200)
    data[8:12] = struct.pack(">I", 0x00000220)
    data[12:16] = struct.pack(">I", 0x00000221)
    data[16:20] = struct.pack(">I", 0x00000500)
    data[0x100:0x110] = b"SEGA MEGA DRIVE "
    data[0x110:0x120] = b"(C)TEST 2026    "
    data[0x120:0x150] = b"BATTLE TEST".ljust(48, b" ")
    data[0x150:0x180] = b"BATTLE TEST".ljust(48, b" ")
    data[0x180:0x18E] = b"GM 00000000-00"
    data[0x1A0:0x1A4] = struct.pack(">I", 0)
    data[0x1A4:0x1A8] = struct.pack(">I", len(data) - 1)
    data[0x1F0:0x1F3] = b"JUE"
    data[0x200:0x204] = b"\x70\x00\x4E\x75"
    checksum = sum(
        int.from_bytes(data[offset : offset + 2], "big")
        for offset in range(0x200, len(data), 2)
    ) & 0xFFFF
    data[0x18E:0x190] = struct.pack(">H", checksum)
    return bytes(data)


class GenesisRomProbeTests(unittest.TestCase):
    def test_parses_header_checksum_and_reset_vectors(self):
        result = parse_rom(make_rom(), "fixture.bin")
        self.assertEqual(result["size_bytes"], 0x400)
        self.assertEqual(result["header"]["title_overseas"], "BATTLE TEST")
        self.assertEqual(result["header"]["region"], "JUE")
        self.assertTrue(result["header"]["checksum_matches"])
        self.assertTrue(result["initial_stack_pointer_in_work_ram"])
        self.assertTrue(result["reset_pc_valid_rom_target"])
        self.assertEqual(
            result["m68k_candidate_entry_points"],
            ["0x00000200", "0x00000220"],
        )
        self.assertEqual(result["m68k_discovery_status"], "vector_seeds_only")
        self.assertEqual(result["z80_discovery_status"], "not_performed")


    def test_sign_extended_initial_stack_pointer_uses_24_bit_bus_alias(self):
        data = bytearray(make_rom())
        data[0:4] = struct.pack(">I", 0xFFFFFFFC)
        result = parse_rom(bytes(data))
        self.assertEqual(result["initial_stack_pointer"], "0xFFFFFFFC")
        self.assertEqual(result["initial_stack_pointer_bus_address"], "0xFFFFFC")
        self.assertTrue(result["initial_stack_pointer_in_work_ram"])

    def test_checksum_mismatch_is_reported_not_repaired(self):
        data = bytearray(make_rom())
        data[0x200] ^= 0x01
        result = parse_rom(bytes(data))
        self.assertFalse(result["header"]["checksum_matches"])

    def test_rejects_short_image(self):
        with self.assertRaises(ProbeError):
            parse_rom(b"\0" * 0x1FF)

    def test_rejects_non_genesis_header(self):
        data = bytearray(make_rom())
        data[0x100:0x104] = b"NOPE"
        with self.assertRaises(ProbeError):
            parse_rom(bytes(data))

    def test_invalid_reset_pc_is_not_added_as_entry_point(self):
        data = bytearray(make_rom())
        data[4:8] = struct.pack(">I", 0x00000400)
        result = parse_rom(bytes(data))
        self.assertFalse(result["reset_pc_valid_rom_target"])
        self.assertNotIn("0x00000400", result["m68k_candidate_entry_points"])

    def test_reads_one_rom_from_zip_without_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("folder/game.bin", make_rom())
            data, source = read_rom_image(path)
            self.assertEqual(data, make_rom())
            self.assertEqual(source, f"{path}!folder/game.bin")

    def test_rejects_ambiguous_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("one.bin", make_rom())
                archive.writestr("two.gen", make_rom())
            with self.assertRaises(ProbeError):
                read_rom_image(path)

    def test_rejects_interleaved_smd(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.smd"
            path.write_bytes(b"not-an-smd")
            with self.assertRaises(ProbeError):
                read_rom_image(path)


if __name__ == "__main__":
    unittest.main()
