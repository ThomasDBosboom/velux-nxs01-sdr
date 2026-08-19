#!/usr/bin/env python3
"""Regression tests for the decoded NXS01 measurement fields."""

import unittest

from decode_velux_rf import co2_ppm, u14


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


if __name__ == "__main__":
    unittest.main()
