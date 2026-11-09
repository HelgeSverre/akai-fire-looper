# Hardware verification

Checks performed on 9 November 2026 with a USB-connected AKAI Fire on macOS. Both MIDI ports were named `FL STUDIO FIRE Jack 1`. The initial checks used commit `365048c`; OLED keepalive was added after measuring idle blanking. Results describe this device and session, not every firmware version.

## Confirmed on the Fire

| Check | Result |
| --- | --- |
| Batched RGB output | All 16 pads in each row lit correctly: red, green, blue and white from top to bottom. |
| OLED encoding and layout | A heading, three text lines and a complete 128×64 border appeared correctly, without clipping or scrambled pixels. |
| Corner pad inputs | Top-left, top-right, bottom-left and bottom-right reported indices 0, 15, 48 and 63, with positive velocities. |
| Button inputs | PATTERN UP/DOWN, GRID LEFT/RIGHT, PLAY, STOP and REC each produced the expected press and release events. IDs were 31, 32, 34, 35, 51, 52 and 53 respectively. |
| Static OLED without refresh | A freshly sent image blanked after approximately eight seconds while the probe remained connected and sent no further display updates. |
| Repeated identical OLED image | Sending the same nonblank frame every two seconds kept it visible for at least 30 seconds; the observer reported no problem. Packet hashes confirmed unchanged image data. |
| Default driver keepalive | A separate probe called `render_to_display()` once. The driver then refreshed identical frames every two seconds, and the observer confirmed the screen stayed visible without a reported problem. |

Raw pad releases arrived as MIDI note-off messages. The public driver still exposes pad presses only; this check does not add a pad-release API.

## OLED keepalive

Idle blanking is consistent with the [DrivenByMoss Fire implementation](https://github.com/git-moss/DrivenByMoss/blob/f9aca50b97efb9d5273e1384b697677b55e309d9/src/main/java/de/mossgrabers/controller/akai/fire/controller/FireDisplay.java), which resends unchanged display data to prevent sleep. The observed eight seconds is approximate and is not a documented universal timeout.

The Python driver now enables keepalive by default. It resends its last submitted frame after two idle seconds; `oled_keepalive=False` disables it. See [the device guide](DEVICE.md#oled-display) for lifecycle and configuration details.

The [keepalive tests](../tests/test_oled_keepalive.py) exercise real driver code with fake MIDI ports: static frames, unsent canvas edits, deadlines after new renders, clearing, failed sends, shutdown during a send, reconnect and opt-out. Those tests establish software behavior; visual hardware checks remain separate.

## Still to verify

- All five encoders in both directions, touch/release on the four main knobs, and SELECT push.
- SHIFT/ALT combinations, remaining buttons, and inputs from every pad.
- Button brightness, track LED states and individual control-bank indicators.
- Snake controls and agreement between its pad and OLED views on hardware.
- Circuit playback and synth-editor output with a receiving instrument explicitly selected.
- Physical unplug/replug recovery.

No JT-4000 was connected during these checks, and no MIDI was sent to the other instrument ports.
