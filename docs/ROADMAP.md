# Roadmap

## Implemented

- Driver and mocks share device callbacks, LED operations and canvas rendering.
- The app framework owns lifecycle, input subscriptions, frame timing and shutdown.
- Optional modes, screen/grid helpers and transport state are available.
- Circuit runs through the framework and has a separate musical clock/note scheduler.
- The JT-4000 editor sends documented CCs and saves local CC snapshots.
- MIDI Scope records controller events, graphs movement and exports CSV.
- The default test discovery includes the Circuit suite and application contracts.

## Next priorities

1. Foreground input dispatch with consistent ordering across hardware and mocks.
2. Pad-release events, followed by a held-note keyboard example.
3. Disconnect notifications and explicit recovery behavior in applications.
4. Physical Fire/JT-4000 verification of the maintained apps and their controls.
5. Circuit timing look-ahead for negative micro offsets and full per-pattern sync-rate scheduling. Current negative offsets clamp to the step boundary; sync rate scales gates, not the track clock.
6. Decide whether to build a full MIDI clip looper. The current looper is a clip-state teaching demo with no instrument I/O.

The legacy sequencer/groovebox scripts are reference experiments. New features should go into the maintained apps rather than another overlapping sequencer.
