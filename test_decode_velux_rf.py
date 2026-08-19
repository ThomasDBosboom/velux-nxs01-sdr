#!/usr/bin/env python3
"""Regression tests for the decoded NXS01 measurement fields."""

import unittest

from decode_velux_rf import HEADERS, co2_ppm, frame_length, u14


class MeasurementDecodeTests(unittest.TestCase):
    def test_sanitized_co2_fixtures(self) -> None:
        calibration_offset = 4000
        fixtures = (
            (bytes.fromhex("00 70"), 416),
            (bytes.fromhex("64 70"), 391),
            (bytes.fromhex("00 71"), 384),
        )
        for encoded, expected in fixtures:
            with self.subTest(encoded=encoded.hex()):
                self.assertEqual(
                    co2_ppm(u14(encoded, 0), calibration_offset), expected
                )

    def test_u14_ignores_interleaved_high_bits(self) -> None:
        self.assertEqual(u14(bytes.fromhex("1f f2"), 0), 14623)
        self.assertEqual(u14(bytes.fromhex("85 f3"), 0), 14725)

    def test_observed_frame_lengths(self) -> None:
        self.assertEqual(frame_length(HEADERS["short"]), 10)
        self.assertEqual(frame_length(HEADERS["button"]), 10)
        self.assertEqual(frame_length(HEADERS["long"]), 64)
        self.assertEqual(frame_length(HEADERS["identify"]), 44)
        self.assertEqual(frame_length(HEADERS["window"]), 44)

    def test_control_headers_use_address_byte_six(self) -> None:
        button = bytes.fromhex("44 b9 83 00 82 4b 2a be 61 43")
        command = bytes.fromhex(
            "44 b9 94 80 82 4a 11 be 61 08 00 80 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
        )
        self.assertEqual(button[6], 0x2A)
        self.assertEqual(command[6], 0x11)
        self.assertEqual(frame_length(button), len(button))
        self.assertEqual(frame_length(command), len(command))


if __name__ == "__main__":
    unittest.main()
