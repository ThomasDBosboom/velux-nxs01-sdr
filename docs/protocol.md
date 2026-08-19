# Observed RF protocol

## Physical layer

The NXS01 indoor climate sensors observed during this experiment transmitted
near 868.187 MHz using 2-FSK at 32,768 symbols/s. The supplied decoder expects
a 300,000 samples/s unsigned 8-bit interleaved-IQ recording.

Five frame families have been observed:

| Family | Header |
|---|---|
| Short/periodic | `44 b9 83 00 82 48` |
| Long telemetry | `44 b9 9e 80 82 4c` |
| Identify command | `44 b9 94 80 82 4c` |
| Sensor button event | `44 b9 83 00 82 4b` |
| Controlled-product command | `44 b9 94 80 82 4a` |

Byte 6 behaves as a transmitter identifier. Do not assume that an identifier
seen in somebody else's capture will apply to your sensor.

## Frame size

Byte 2 encodes a count of 16-bit words after a four-byte prefix:

```text
frame_length = 4 + 2 * (payload[2] & 0x7f)
```

This produces exactly 10 bytes for `0x83`, 44 bytes for `0x94`, and 64 bytes
for `0x9e`. Earlier decoder versions printed receiver noise after byte 9 of
short frames because they did not apply this length field.

## Long-frame measurements

Offsets below are zero-based byte offsets from the beginning of the matched
long-frame header.

| Measurement | Decode |
|---|---|
| Temperature | `((payload[15] & 0x7f) - 24) / 4` degrees C |
| Relative humidity | `(payload[17] & 0x7f) * 2` percent |
| CO2 raw word | `(payload[28] & 0x7f) + 128 * (payload[29] & 0x7f)` |
| CO2 | `round(calibration_offset - raw_word / 4)` ppm |
| Battery candidate | `payload[14] & 0x7f` (tentative ordinal code) |

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

The battery candidate was discovered by comparing an official UI indication
against synchronized RF frames. A sensor shown as full remained at code `9`;
a visibly depleted sensor produced `6` or `7`; and a third sensor produced
`8`. This is promising but not yet calibrated to voltage or percentage. A
battery replacement while capturing is the required confirmation.

## Cadence and network slots

Periodic traffic follows a very stable schedule:

- A network opportunity occurs approximately every 18.997 seconds.
- Long telemetry normally arrives every third opportunity, about 56.992
  seconds apart.
- The CO2 field changes approximately every five long frames, consistent with
  the product's roughly five-minute CO2 update.
- Multiple sensors occupy repeatable sub-slots a few hundred milliseconds
  apart.

Identify commands appeared in the target sensor's normal slot. Three repeated
requests were observed in three successive slots in one experiment, while a
second experiment coalesced three UI taps into one command.

## Failed-sensor comparison

A discarded sensor known to remain at the UI's 5,000 ppm ceiling was captured
alongside two healthy sensors. Its temperature and humidity remained valid,
but its CO2 reference was only tens of counts instead of roughly 14,000 and
one optical diagnostic word was around 1,800 instead of roughly 500. This
supports the interpretation of bytes 18-23 as optical-path diagnostics and
suggests that 5,000 ppm can represent sensor saturation or failure rather
than a real concentration.

## Protected tail

Bytes 32-63 of long frames have near-random avalanche behaviour. Pairs with an
identical low-seven-bit telemetry prefix differed by approximately 128 of 256
tail bits on average. The tail is therefore more likely to contain encrypted,
nonce-dependent or keyed integrity data than additional plain measurements.

See [Control traffic](control.md) for the active Identify and physical-button
experiments.

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
6. Length-aware byte packing and field extraction.

It tolerates up to four header-bit errors, but it does not yet validate a CRC
or other integrity field. A plausible-looking damaged payload is therefore
possible and should not drive safety-critical automation.

## Open questions

- Where is the CRC, checksum or MIC, and what algorithm does it use?
- What status or acknowledgement is carried by periodic short frames?
- What do the optical diagnostic words represent?
- How does the tentative battery code map to voltage or percentage?
- Where is the OPEN/CLOSE/CENTRE action encoded in protected control frames?
- Is the 868.187 MHz estimate consistent across hardware and regions?
- Does the CO2 slope and field layout hold across firmware revisions?
- Can robust streaming demodulation run cheaply on a Home Assistant host?
