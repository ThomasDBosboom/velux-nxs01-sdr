# Control traffic

The indoor climate sensor has physical buttons that can control associated
windows. Controlled experiments revealed a fast two-packet relay path. The
addresses below are described symbolically because they are specific to an
installation.

```text
sensor button event
  44 b9 83 00 82 4b SS ...
  approximately 26-28 ms later
controlled-product command
  44 b9 94 80 82 4a WW ...
```

`SS` is the sensor's one-byte RF address and `WW` is the controlled product's
address. Four alternating OPEN/CLOSE presses and three dedicated CENTRE
presses all reproduced this topology.

The short button event is exactly 10 bytes. Its final two bytes changed over
time and sometimes repeated across different actions, so they appear to
include rolling or protected state rather than a plain button number.

The relayed controlled-product command is exactly 44 bytes. The low seven bits
of byte 11 produced this small dataset:

| Physical button | Observed byte 11 |
|---|---:|
| OPEN | `0` in 2/2 captures |
| CLOSE | `1` in 2/2 captures |
| CENTRE | `0` in 3/3 captures |

This field is **not a complete action opcode**: the dedicated CENTRE capture
falsified that early hypothesis. It may mean CLOSE versus non-CLOSE, or it may
be a flag/counter that happened to correlate with direction. The actual action
is probably represented in the protected part of the command.

## Identify

Using the manufacturer's Identify UI generated another 44-byte family:

```text
44 b9 94 80 82 4c SS ...
```

Byte 6 matched the selected sensor's RF address. Combined with the physical
button experiment, the most plausible directions are:

```text
button event: sensor -> gateway
window command: gateway -> controlled product
Identify: gateway -> sensor
```

The directions are an inference from addressing, timing and the 28 ms relay;
they have not been confirmed with separate receivers at each endpoint.

## Safe next experiments

- Capture a fresh-battery replacement to calibrate the battery code.
- Press CENTRE while a window is moving, once in each direction, when weather
  permits.
- Capture immediately after battery insertion to look for association and
  startup traffic.
- Compare the same control action across two controlled products to separate
  address, rolling state and action-dependent bits.

This repository intentionally remains receive-only. It does not construct or
transmit control packets.
