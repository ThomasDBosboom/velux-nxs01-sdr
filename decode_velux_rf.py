#!/usr/bin/env python3
"""Experimental receive-only decoder for VELUX ACTIVE NXS01 RF captures."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly


HEADERS = {
    "short": bytes.fromhex("44 b9 83 00 82 48"),
    "long": bytes.fromhex("44 b9 9e 80 82 4c"),
}


def byte_bits(value: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(value, dtype=np.uint8))


def u14(payload: bytes, offset: int) -> int:
    """Decode a little-endian value stored in two low-seven-bit symbols."""
    return (payload[offset] & 0x7F) | ((payload[offset + 1] & 0x7F) << 7)


def co2_ppm(reference: int, calibration_offset: float) -> int:
    """Convert the calibrated 14-bit CO2 word to whole ppm."""
    return round(calibration_offset - reference / 4)


def find_bursts(raw: np.memmap, sample_rate: int) -> list[tuple[float, float, float]]:
    block = max(1, sample_rate // 2000)
    usable = raw.size // (2 * block) * (2 * block)
    power_chunks = []
    blocks_per_chunk = 60_000
    bytes_per_chunk = blocks_per_chunk * block * 2
    for offset in range(0, usable, bytes_per_chunk):
        end = min(usable, offset + bytes_per_chunk)
        iq = raw[offset:end].reshape(-1, block, 2).astype(np.float32) - 127.5
        power = np.mean(iq[:, :, 0] ** 2 + iq[:, :, 1] ** 2, axis=1)
        power_chunks.append((10 * np.log10(power + 1e-9)).astype(np.float32))
    if not power_chunks:
        return []
    power_db = np.concatenate(power_chunks)
    threshold = float(np.median(power_db) + 10.0)
    active = power_db > threshold
    active[1:-1] |= active[:-2] & active[2:]
    edges = np.diff(np.r_[False, active, False].astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    result = []
    for start, stop in zip(starts, stops):
        duration = (stop - start) * block / sample_rate
        if duration >= 0.001:
            result.append(
                (
                    start * block / sample_rate,
                    stop * block / sample_rate,
                    float(np.max(power_db[start:stop])),
                )
            )
    return result


def decode_burst(
    raw: np.memmap, start: float, stop: float, sample_rate: int
) -> tuple[str, int, int, bytes] | None:
    pad = 0.003
    first = max(0, int((start - pad) * sample_rate))
    last = min(raw.size // 2, int((stop + pad) * sample_rate))
    pairs = raw[first * 2 : last * 2].reshape(-1, 2).astype(np.float32)
    signal = (pairs[:, 0] - 127.5) + 1j * (pairs[:, 1] - 127.5)

    signal = resample_poly(signal, 32_768, 37_500)
    discriminator = np.angle(signal[1:] * np.conj(signal[:-1]))

    best: tuple[int, float, str, int, int, np.ndarray] | None = None
    for phase in range(8):
        length = (discriminator.size - phase) // 8
        if length < 48:
            continue
        symbols = discriminator[phase : phase + length * 8].reshape(-1, 8).mean(axis=1)
        midpoint = (np.percentile(symbols, 25) + np.percentile(symbols, 75)) / 2
        base_bits = (symbols > midpoint).astype(np.uint8)
        for inverted in (0, 1):
            bits = base_bits ^ inverted
            for family, header in HEADERS.items():
                wanted = byte_bits(header)
                correlation = np.convolve(
                    bits.astype(np.int16) * 2 - 1,
                    (wanted.astype(np.int16) * 2 - 1)[::-1],
                    mode="valid",
                )
                index = int(np.argmax(correlation))
                bit_errors = (wanted.size - int(correlation[index])) // 2
                confidence = float(np.mean(np.abs(symbols - midpoint)))
                candidate = (
                    bit_errors,
                    -confidence,
                    family,
                    phase,
                    inverted,
                    bits[index:],
                )
                if best is None or candidate[:2] < best[:2]:
                    best = candidate

    if best is None:
        return None
    errors, _, family, phase, _, bits = best
    byte_count = min(64, bits.size // 8)
    payload = np.packbits(bits[: byte_count * 8]).tobytes()
    return family, errors, phase, payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--sample-rate", type=int, default=300_000)
    parser.add_argument("--sensor", type=lambda value: int(value, 0))
    parser.add_argument("--family", choices=HEADERS)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--stop", type=float, default=float("inf"))
    parser.add_argument(
        "--co2-offset",
        action="append",
        default=[],
        metavar="SENSOR:OFFSET",
        help="add a per-sensor CO2 calibration, e.g. 0x2a:4196",
    )
    args = parser.parse_args()

    co2_offsets: dict[int, float] = {}
    for spec in args.co2_offset:
        sensor_text, offset_text = spec.split(":", 1)
        co2_offsets[int(sensor_text, 0)] = float(offset_text)

    raw = np.memmap(args.capture, dtype=np.uint8, mode="r")
    bursts = find_bursts(raw, args.sample_rate)
    print(f"bursts={len(bursts)}")
    for start, stop, peak in bursts:
        if start < args.start or start > args.stop:
            continue
        decoded = decode_burst(raw, start, stop, args.sample_rate)
        if decoded is None:
            continue
        family, errors, phase, payload = decoded
        if errors > 4:
            continue
        sensor = payload[6] if len(payload) > 6 else -1
        if args.sensor is not None and sensor != args.sensor:
            continue
        if args.family is not None and family != args.family:
            continue
        print(
            f"{start:8.3f}-{stop:8.3f}s peak={peak:5.1f}dB "
            f"{family} errors={errors} phase={phase} sensor=0x{sensor:02x}"
        )
        print("  " + payload.hex(" "))
        if family == "long" and len(payload) > 31:
            temperature = ((payload[15] & 0x7F) - 24) / 4
            humidity = (payload[17] & 0x7F) * 2
            ir_samples = tuple(u14(payload, offset) for offset in (18, 20, 22))
            co2_reference = u14(payload, 28)
            calibrated_co2 = (
                co2_ppm(co2_reference, co2_offsets[sensor])
                if sensor in co2_offsets
                else None
            )
            co2_text = (
                f"co2={calibrated_co2}ppm "
                if calibrated_co2 is not None
                else "co2=uncalibrated "
            )
            print(
                f"  temperature={temperature:.2f}C humidity={humidity}% "
                f"{co2_text}word_count={payload[2] & 0x7F} "
                f"ir_samples={ir_samples} co2_reference={co2_reference} "
                f"five_minute_field={payload[28:32].hex(' ')}"
            )


if __name__ == "__main__":
    main()
