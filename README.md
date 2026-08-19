# VELUX ACTIVE NXS01 SDR decoder

Experimental, receive-only tooling and protocol notes for the VELUX ACTIVE
with NETATMO NXS01 indoor climate sensor.

This project grew out of a practical question: can an inexpensive RTL-SDR
receive the temperature, humidity and CO2 measurements that the sensor makes
available through VELUX/HomeKit? The answer is increasingly yes: telemetry,
frame sizes, device addresses, Identify traffic and sensor-button window
control have all been observed. CO2 needs a per-sensor calibration offset.

## Current status

- Observed carrier: approximately **868.187 MHz**
- Modulation: **2-FSK**
- Symbol rate: **32,768 symbols/s**
- Five observed frame families, including telemetry and control traffic
- Frame length decoded as `4 + 2 * (byte_2 & 0x7f)`
- Temperature and relative humidity: decoded and cross-checked
- CO2: decoded with a shared slope and a per-sensor additive offset
- Battery: likely a small ordinal code, pending a fresh-battery experiment
- Identify and window-button routing: structurally decoded
- Home Assistant integration: not implemented yet
- Frame integrity/CRC: not identified yet

The protocol is proprietary and this work is based on observations from a
small number of sensors. Treat every field assignment as experimental.

## Quick start

You need an RTL-SDR-compatible receiver, `rtl_sdr`, Python 3, NumPy and SciPy.
The example sample rate is important because the decoder currently assumes
unsigned 8-bit interleaved IQ (`cu8`).

```shell
rtl_sdr -f 868187000 -s 300000 -g 40 capture.cu8
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 decode_velux_rf.py capture.cu8 --family long
```

Filter one transmitter with `--sensor 0x2a` (replace this example with the
identifier printed for your sensor). After learning its CO2 offset,
provide it on the command line:

```shell
python3 decode_velux_rf.py capture.cu8 \
  --sensor 0x2a \
  --family long \
  --co2-offset 0x2a:OFFSET
```

The sensor identifier and offset are intentionally not built into this public
version. See [the protocol notes](docs/protocol.md) for field formulas and
calibration, and [the control notes](docs/control.md) for the observed
sensor-to-gateway-to-window exchange.

## Tests

```shell
python3 -m unittest -v
```

## Sharing captures safely

Raw RF recordings can be large and can include transmissions from unrelated
nearby devices. This repository therefore ignores common IQ capture formats.
Before sharing a capture, trim it to the relevant bursts and consider whether
device identifiers or unrelated traffic should be removed.

Only receive signals from equipment you own or are permitted to examine, and
follow the radio and privacy rules that apply where you live. This project
does not transmit, pair with, or control a VELUX product.

## Contributions

Independent captures are especially useful for validating the PHY, finding
the frame integrity check, testing whether the CO2 slope holds across devices,
and turning the decoder into a streaming/Home Assistant component. Please do
not post credentials, home addresses, network details, or untrimmed captures.

VELUX, VELUX ACTIVE, NETATMO and HomeKit are trademarks of their respective
owners. This project is unofficial and is not affiliated with or endorsed by
them.
