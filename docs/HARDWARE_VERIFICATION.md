# Hardware verification

Checks performed on 9 November 2026 with a USB-connected AKAI Fire on macOS. Both MIDI ports were named `FL STUDIO FIRE Jack 1`. The initial checks used commit `365048c`; OLED keepalive was added after measuring idle blanking. Results describe this device and session, not every firmware version.

## Confirmed on the Fire

| Check | Result |
| --- | --- |
| Batched RGB output | All 16 pads in each row lit correctly: red, green, blue and white from top to bottom. |
| OLED encoding and layout | A heading, three text lines and a complete 128×64 border appeared correctly, without clipping or scrambled pixels. |
| Corner pad inputs | Top-left, top-right, bottom-left and bottom-right reported indices 0, 15, 48 and 63, with positive velocities. |
| Button inputs | PATTERN UP/DOWN, GRID LEFT/RIGHT, PLAY, STOP and REC each produced the expected press and release events. IDs were 31, 32, 34, 35, 51, 52 and 53 respectively. |
| Encoder turns | VOLUME, PAN, FILTER, RESONANCE and SELECT reported both clockwise and counterclockwise turns with IDs 16, 17, 18, 19 and 118. Main-knob speed values ranged from 1 to 10 across this check; SELECT reported 1. |
| Encoder touch and SELECT push | Each main knob produced balanced touch/release events. SELECT produced four matching press/release pairs with button ID 25. |
| Modifier snapshots | Top-left pad callbacks correctly reported SHIFT-only, ALT-only and neither modifier. Modifier release callbacks reported the cleared state. |
| Button and bank LED output | PLAY, REC and STEP lit, and all four bank indicators lit with `CONTROL_BANK_ALL_ON`. Individual bank selection and the full button color/brightness range still need separate checks. |
| Track LED addresses and values | Corrected CC addresses from `0x65–0x68` to `0x28–0x2B`. The observer confirmed dim red, dim green, bright red and bright green from top to bottom, including the brightness difference. Exact-message tests cover all four addresses, values 0–4 and clearing. |
| USER 2 bank selection | `CONTROL_BANK_USER2` (`0x03`) lit USER 2 on this Fire. The existing constant was retained; this observation differs from the selector table in the [SEGGER reference](https://blog.segger.com/decoding-the-akai-fire-part-2/), which labels `0x03` as USER 1. |
| Snake app | The observer reported responsive play, matching pad/OLED views and no visual problem. Recorded events include all four direction buttons, four pauses, four STOP resets, crash/retry transitions and a highest score of 3. |
| Circuit preview after batching | Recorded mode changes cover NOTE, STEP EDIT, MIXER, PATTERN and SETTINGS, plus PLAY/STOP, across 124.5 seconds. The observer reported that most controls responded. No SOLO track-selection events were captured in this run, and detailed OLED readability was not explicitly confirmed. |
| Circuit NOTE layout and track selection | A later focused check confirmed SOLO 2 selected `NOTE T2` and the four content rows were readable. The observer found the right-aligned status against the screen edge. Measurement used grayscale glyph advances, which underestimated `STOP 120` by four pixels on the monochrome canvas; fitting and header alignment now use monochrome metrics, with a shared four-pixel horizontal inset. The observer reported that the updated layout looked better. |
| Circuit Mixer layout and mute feedback | After correcting mute feedback, the observer confirmed the first mute pad toggled the OLED marker and pad color correctly in both directions. All four track rows and channel labels fit on the OLED. |
| Circuit Patterns interaction | The observer found the original chain endpoint and track selection unintuitive. After replacing it with row-owned pattern selection and SHIFT-held endpoints, a guided check covered selecting a track's pattern, waiting on an endpoint, completing a chain, changing another track, and cancelling an unfinished selection. The observer reported that this made more sense; no new mismatch was reported. |
| Circuit Settings layout | The observer confirmed all menu labels, highlights and scrolling rows were visible. Occasional apparently missed counterclockwise SELECT steps were reported in Circuit. |
| Isolated SELECT steps | A quiet probe recorded exactly ten clockwise raw CC 118 values of 1 and ten counterclockwise values of 127, each decoded once with velocity 1. The observer reported that the counter test worked. The Circuit-specific missed-step report is not reproduced or considered resolved by this isolated test. |
| Circuit SELECT editing | After adding press-to-edit, the observer confirmed BPM edit entry, three clockwise and three counterclockwise increments, press-to-finish, and navigation to Swing and back worked well. The edit screen was readable, with no missed step reported in this check. GRID navigation currently finishes live editing; the framework also supports retaining edit mode when navigating to another editable value. |
| Circuit STEP layout | After a guided pitch-entry and velocity-edit check, the observer confirmed all text was readable: header, notes, velocity/gate, probability/microtiming and the bottom edit-parameter line. This confirms readability; the response did not separately confirm each expected value change. |
| Static OLED without refresh | A freshly sent image blanked after approximately eight seconds while the probe remained connected and sent no further display updates. |
| Repeated identical OLED image | Sending the same nonblank frame every two seconds kept it visible for at least 30 seconds; the observer reported no problem. Packet hashes confirmed unchanged image data. |
| Default driver keepalive | A separate probe called `render_to_display()` once. The driver then refreshed identical frames every two seconds, and the observer confirmed the screen stayed visible without a reported problem. |

Raw pad releases arrived as MIDI note-off messages. The public driver still exposes pad presses only; this check does not add a pad-release API.

## OLED keepalive

Idle blanking is consistent with the [DrivenByMoss Fire implementation](https://github.com/git-moss/DrivenByMoss/blob/f9aca50b97efb9d5273e1384b697677b55e309d9/src/main/java/de/mossgrabers/controller/akai/fire/controller/FireDisplay.java), which resends unchanged display data to prevent sleep. The observed eight seconds is approximate and is not a documented universal timeout.

The Python driver now enables keepalive by default. It resends its last submitted frame after two idle seconds; `oled_keepalive=False` disables it. See [the device guide](DEVICE.md#oled-display) for lifecycle and configuration details.

The [keepalive tests](../tests/test_oled_keepalive.py) exercise real driver code with fake MIDI ports: static frames, unsent canvas edits, deadlines after new renders, clearing, failed sends, shutdown during a send, reconnect and opt-out. Those tests establish software behavior; visual hardware checks remain separate.

## Remaining driver-level hardware checks

- Live reconnect of an existing driver instance after physical unplug/replug, including resumed input and OLED keepalive. The earlier recovery check opened a fresh driver after reconnecting.
- Full button color/brightness range and the remaining individual control-bank indicators. Track LED values and USER 2 are confirmed; this does not establish every button/bank mapping.
- All 64 pad input indices, remaining button press/release pairs, and SHIFT+ALT held together. Only corner-pad indices and the listed controls were checked systematically.
- A sustained mixed-input/output run to check for stalls or missed events. The short post-batching Circuit session is useful evidence, but is not an extended load test.

### Deferred application checks

Circuit STEP copy/paste/clear is inconclusive: the observer was unsure of the result and chose to stop application testing. The captured output showed copy operations but did not establish a completed paste/clear sequence. No pass or confirmed defect is recorded. Detailed edited-value feedback, musical timing and further application workflows remain outside the completed hardware checks.

Circuit playback and synth-editor output still need a receiving instrument explicitly selected. These are integration checks rather than tests of the Fire driver.

No JT-4000 was connected during these checks, and no MIDI was sent to the other instrument ports.

## Circuit traffic and recovery

The first Circuit preview left the Fire unresponsive to both output and input. The Python process was still rendering and polling MIDI. A subsequent quiet probe also failed to produce visible output or input events. Unplugging and reconnecting the Fire restored its startup animation; a fresh probe then displayed the RGB/OLED check and captured PLAY press/release.

An offline capture through the real driver found 74 pad SysEx messages per idle Note-mode frame, or about 2,220 per second at 30 FPS. Circuit cleared the pads and repainted them individually. The grid renderer now composes the final colors in memory and sends one complete pad batch per frame. [Regression tests](../tests/test_circuit_hardware_output.py) check the packet count and final colors in every mode, plus batched clearing on mode changes.

After this change and the USB restart, Circuit stayed responsive during the follow-up described above. Excessive message traffic is the leading explanation for the original lockup, but the test did not establish a firmware limit or rule out every other cause.

## Circuit mute feedback

The focused Mixer check exposed a missing status field: pressing the first mute pad changed `Track.muted`, but the sequencer's display snapshot omitted it. The OLED marker and pad renderer instead checked `enabled`, a separate property. The snapshot now includes `muted`, and both views show a muted or disabled track before considering its solo flag. An input-to-display regression verifies the mute toggle, status, OLED marker, pad color and unchanged neighboring track indicators. The observer confirmed the corrected marker and color toggled correctly on hardware.
