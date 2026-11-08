# Roadmap

The project's focus is a reusable Python device library, application framework
and testing toolkit for custom AKAI Fire applications. Example apps exercise
those APIs and demonstrate patterns for users to build on.

## Available building blocks

- Driver and mocks share device callbacks, LED operations and canvas rendering.
- The app framework owns lifecycle, input subscriptions, frame timing and shutdown.
- Optional modes, screen/grid helpers and transport state are available.
- Headless mocks support simulated input and assertions about controller/MIDI output.
- Interactive pygame and terminal mocks support development from a checkout.
- Tests cover the packages, mocks and maintained example applications.

## Library and framework priorities

1. Foreground input dispatch with consistent ordering across hardware and mocks.
2. Pad-release events with parity across controller implementations.
3. Disconnect notifications and explicit application recovery hooks.
4. A small ownership API for app-created resources and subscriptions.
5. Broader physical-hardware validation of device behavior and mock parity.

## Example-app follow-ups

- Add a held-note keyboard example once pad-release events are available.
- Validate Circuit and the JT-4000 editor against physical instruments.
- Add Circuit timing look-ahead for negative micro offsets and full per-pattern
  sync-rate scheduling. Current negative offsets clamp to the step boundary;
  sync rate scales gates, not the track clock.
- Decide whether to extend the clip-state teaching demo into a MIDI clip looper.
  It currently has no instrument I/O.

Synth profiles, musical clocks and recording/persistence formats stay with the
applications until several real consumers justify a shared abstraction. Legacy
sequencer/groovebox scripts remain reference experiments.
