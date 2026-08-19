# Observed RF protocol

## Physical layer

The NXS01 indoor climate sensors observed during this experiment transmitted
near 868.187 MHz using 2-FSK at 32,768 symbols/s. The supplied decoder expects
a 300,000 samples/s unsigned 8-bit interleaved-IQ recording.

Two frame families have been observed:

| Family | Header |
|---|---|
| Short | `44 b9 83 00 82 48` |
| Long telemetry | `44 b9 9e 80 82 4c` |

Byte 6 behaves as a transmitter identifier. Do not assume that an identifier
seen in somebody else's capture will apply to your sensor.

## Long-frame measurements

Offsets below are zero-based byte offsets from the beginning of the matched
long-frame header.

| Measurement | Decode |
|---|---|
| Temperature | `((payload[15] & 0x7f) - 24) / 4` degrees C |
| Relative humidity | `(payload[17] & 0x7f) * 2` percent |
| CO2 raw word | `(payload[28] & 0x7f) + 128 * (payload[29] & 0x7f)` |
| CO2 | `round(calibration_offset - raw_word / 4)` ppm |

The most important CO2 discovery is that the high bit of each on-air byte is
not part of the numeric value. Masking those bits reveals a little-endian
14-bit word. Without the mask, nearby ppm readings appear non-monotonic and
look encrypted.

The observed CO2 slope is **-0.25 ppm per raw count**. The additive offset is
per sensor and can move during the product's manual CO2 recalibration. Three
post-calibration observations from one sensor independently produced the same
offset; the exact device ID and offset are omitted here because they are
installation-specific.

Bytes 18-23 contain three more 14-bit words that change at the faster telemetry
cadence. They appear related to the optical/infrared measurement path, but
their exact meaning is not established. The calibrated CO2 word at bytes
28-29 changes at roughly the product's CO2 update cadence.

## Learning a CO2 offset

1. Let the sensor finish any manual recalibration.
2. Record a long RF frame while the official app or HomeKit shows the CO2 ppm.
3. Calculate `raw_word` from bytes 28 and 29 after masking both high bits.
4. Calculate `calibration_offset = displayed_ppm + raw_word / 4`.
5. Repeat for several CO2 updates. The resulting offsets should agree.
6. Pass the stable result as `--co2-offset SENSOR_ID:OFFSET`.

Do not learn the offset while the UI reports that the sensor is recalibrating:
the value is expected to move during that process.

## Decoder pipeline

The proof-of-concept decoder performs:

1. Power-based burst detection.
2. Polyphase resampling to 262,144 samples/s (8 samples per symbol).
3. Quadrature frequency discrimination.
4. Eight-phase symbol timing search, with both polarities tried.
5. Correlation against the known 48-bit frame-family headers.
6. Byte packing and field extraction.

It tolerates up to four header-bit errors, but it does not yet validate a CRC
or other integrity field. A plausible-looking damaged payload is therefore
possible and should not drive safety-critical automation.

## Open questions

- Where is the CRC, checksum or MIC, and what algorithm does it use?
- What are the short frames used for?
- What do the optical diagnostic words represent?
- Is the 868.187 MHz estimate consistent across hardware and regions?
- Does the CO2 slope and field layout hold across firmware revisions?
- Can robust streaming demodulation run cheaply on a Home Assistant host?
