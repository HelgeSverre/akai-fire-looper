# Circuit sequencer

A four-track MIDI sequencer controlled from the Fire. It has a scale keyboard, step editor, mixer, pattern chains, scenes, and settings. It sends MIDI to external instruments; it does not synthesize audio.

```sh
uv run python -m examples.apps.circuit
```

The first run prints MIDI ports and starts in preview mode. Select exact port names to send/record MIDI:

```sh
CIRCUIT_MIDI_OUTPUT="Your instrument" CIRCUIT_MIDI_INPUT="Your keyboard" \
  uv run python -m examples.apps.circuit
```

Input is optional. The Fire port is reserved for the controller and rejected as an instrument port. Track channels start at 10 (drums), 1 (bass), 2 (lead), and 3 (pad); change them in Settings.

## Make a pattern

1. Press SOLO 1–4 to choose a track and NOTE for the scale keyboard.
2. Press REC and play the bottom two pad rows to record notes into the running pattern. Pad auditions last 300 ms because the driver currently exposes presses without releases.
3. Press STOP, then PLAY to hear the pattern.
4. Press STEP to select a step on row 1. On row 2, pads 1–4 select velocity, timing, pitch, and length. The bottom two rows set the selected value. Pitch creates/replaces a single note; velocity applies to every note in that step.
5. Row 2 pads 9–12 copy, paste, clear, or duplicate the selected step.

The step editor currently addresses the first 16 steps; patterns can store/play up to 32. Timing edits store −6…+6 micro offsets, but playback clamps negative offsets to the boundary because there is no look-ahead engine. Positive offsets delay notes by up to 10% of a step. Gate lengths end independently of the next step tick. Pattern sync rate currently scales gate durations, not the track's step clock.

## Controls

| Control | Action |
| --- | --- |
| PLAY / REC / STOP | Toggle playback / record selected track / stop and silence |
| NOTE / STEP / DRUM / PERFORM | Keyboard / step editor / mixer / patterns |
| SOLO 1–4 | Select track |
| BROWSER | Toggle Settings |
| GRID LEFT/RIGHT | Octave in Note mode; navigation in other modes |
| VOLUME / FILTER / PAN | Mode-specific controls; Note mode uses BPM / swing / quantization |
| SELECT encoder | First encoder action in the active mode; menu navigation in Settings |
| SELECT button | Execute selected Settings action |

In Settings, VOLUME/SELECT navigates and FILTER/PAN changes the value. Save/Load Settings stores configuration at `~/.circuit_sequencer_settings.json`; it does not save a full song. Mixer solo uses the track's persisted `soloed` state. External keyboard note-ons record into the selected recording track; input is not forwarded as general MIDI-through.

## Automated demo and tests

```sh
uv run python -m examples.apps.circuit.demo_e2e --demo modes
uv run python -m examples.apps.circuit.test_pygame_smoke
uv run python -m unittest discover
```

The app reuses `AkaiFireApp` for display refresh and controller ownership. Its musical clock and note scheduler live in `core/`; UI modes live in `ui/modes/`. [spec.md](spec.md) is historical design material, not a promise that every proposed feature is implemented. Physical timing and synth integration still need hardware testing.
