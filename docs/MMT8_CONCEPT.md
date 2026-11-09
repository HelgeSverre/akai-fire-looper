# Eight Track: an MMT-8-inspired Fire application

Design exploration, 10 November 2026. This application is proposed, not implemented.
The working assumption is that “Alesis MT8” means the **Alesis MMT-8** MIDI recorder.

## The experience

Record a musical phrase, add another instrument, bring tracks in and out, and turn
those variations into a song. The main screen should answer three questions:
what is playing, what will record, and what happens when the loop ends?

The MMT-8 groups eight MIDI tracks into a **part**. A **song** is an ordered list of
parts, with a track-enable selection stored for each song step. Tracks can retain
the MIDI channels of their recorded events or redirect playback to a chosen
channel. Its recording workflow includes record-ready, count-in and a selected
record track; recording over a populated track replaces its contents. These are
useful foundations for the design. See the [original Alesis manual](https://www.smemmusic.ch/sites/default/files/2025-10/alesis-hr16_hr16b_mmt8_manual.pdf),
MMT-8 sections “Introduction”, “Recording a Part”, “Editing and Creating a Song”
and “MIDI Channel”.

Our version would retain that small vocabulary and add visible pending actions,
undoable takes, named parts and safe project saves. It would not emulate tape
backup, the numeric keypad, memory limits or the original file format.

## One reliable home view

Use the 16 pad columns as **eight vertical strips, two columns per track**. Track
positions stay fixed. In the PERFORM view, the upper three rows show six cells of
musical activity for each track. The bottom row has two independent controls:

| Pad row | Track 1, columns 1–2 | Track 2, columns 3–4 | … | Track 8, columns 15–16 |
| --- | --- | --- | --- | --- |
| 1–3 | Activity / loop position | Activity / loop position | … | Activity / loop position |
| 4 | Select · Mute | Select · Mute | … | Select · Mute |

The activity cells are a coarse musical overview, not a velocity meter or a
16-step editor. The OLED shows the selected track's finer note timeline.
Selecting a track never changes whether it is audible. Muting never changes
which track is selected. The selected pad is white; mute pads show enabled/dim
states in track colors. An armed track pulses red on its select pad, and the
OLED spells out its state so color is not the only cue.

This layout needs a usability prototype: an unlabeled pad grid cannot explain
“Select · Mute” by itself. Show that legend on entry, repeat the selected action
on the OLED, and ship a one-page control map. The acceptance check is whether
someone can select, mute and record a second track after one demonstration.

The OLED would reserve fixed regions for transport/tempo, selected track and
route, a small timeline, and one status or instruction line. For example:

```text
P01  PLAY     120
T2 BASS  > Ch 02
[note timeline]
BAR 2/4   NEXT P03
```

Use the existing measured text/layout helpers and inset both header edges.
Pending changes should read `NEXT P03`, `REC NEXT BAR` or `TAKE SAVED`, with no
invisible gesture timeout.

## Core controls

| Control | Proposed behavior |
| --- | --- |
| PLAY | Start or resume playback. If record-ready, start the count-in and take. |
| STOP | Stop and release sounding notes. A second press rewinds to the start. |
| REC, stopped | Arm/disarm the selected track. Show take mode and length before PLAY. |
| REC, playing | Queue a take for the next bar; pressing again before that boundary cancels it. |
| REC, recording | Finish the take and continue playback. |
| SELECT | Select a track; press to open its settings. Within settings, press to edit/confirm. |
| PERFORM | Return to the eight-track overview. |
| PATTERN | Open the part browser. Select a part immediately when stopped or queue it when playing. |
| BROWSER | Project actions, routing and the song arranger. |
| ALT | Undo the last completed take or edit, with a visible description. |

Default recording is one pass through the part. A new take is staged separately
and replaces the old track only when completed; undo restores the old take.
Overdub is an explicit track setting. Use a four-bar default and a visible
length setting before recording. Free-length first takes can follow later.

The four main knobs get stable home-view functions: tempo, playback quantize,
swing and selected-track transpose. Show the parameter name and value when
turned. Quantize, swing and transpose are reversible playback settings; recorded
timing and pitches remain available. Length and routing live in SELECT settings,
where an accidental encoder turn cannot truncate a part or reroute it.

## Parts into songs

The part browser presents named slots; copying a part creates an independent
variation. In the song arranger, each entry contains a part, repeat count and
eight-track enable mask. For example, reuse one part as:

| Entry | Part | Repeats | Enabled tracks |
| --- | --- | --- | --- |
| Intro | Groove A | 2 | Drums, pad |
| Verse | Groove A | 4 | Drums, bass, pad |
| Chorus | Groove A | 4 | All eight |
| Break | Groove A | 2 | Bass, lead |

Editing an entry's mask is explicit. Live mute changes during song playback are
temporary overrides, shown as such; they do not silently rewrite the arrangement.
Part changes commit at the current part's end. Track mutes are immediate by
default. The OLED always distinguishes the current part from a queued part.

## Framework fit and missing pieces

Reuse `AkaiFireApp`, `@on.pad`, `@on.button`, `@on.encoder`, foreground `tick`,
grid helpers, screen layouts and the SELECT menu editing pattern. Decorated
handlers issue recorder commands; `on_update` draws an engine snapshot.

Music scheduling belongs to a dedicated engine with a monotonic clock, outside
the display loop. Timestamp external MIDI at ingress, preserve event order,
capture note durations and sustain/controller messages, and schedule playback
independently of OLED rendering. A single engine owns transport, take boundaries
and sounding-note bookkeeping. Do not mirror that state in a second transport
mixin state machine.

The existing Circuit engine provides useful implementation examples, but its
`_record_input` and `record_note` currently capture positive note events into
steps. It is not a complete real-time MIDI recorder to rename and reuse.

Two input gaps matter if the Fire also becomes the playing keyboard:

- The driver currently dispatches positive pad presses; the framework has no
  public pad-release event. Sustained pad notes require a compatible release
  path through hardware, mocks and decorators, verified on the physical Fire.
- Queued app events have no ingress timestamp. Timing a performed note when its
  foreground handler runs would add frame delay. Accurate Fire recording needs
  timestamps captured before that queue and carried with the event.

An external MIDI keyboard can supply held notes independently of those Fire
gaps. Start there, then add NOTE/DRUM playing views after releases and timestamps
are verified. Fire pads should initially remain reliable transport/performance
controls rather than pretending to capture held notes.

Project storage should use versioned files, validated loads, atomic replacement
and recoverable take history. Select instrument ports explicitly and keep them
separate from the Fire control port. Handle note-off and sustain cleanup on
mute, stop, part changes, output changes and shutdown. Overlapping notes on the
same output/channel need ownership accounting so muting one track does not cut
off another track's note.

## Build and verification order

1. **Playable overview:** seeded eight-track demo, part switching, track
   selection/muting, OLED timeline and optional built-in preview sound. Prototype
   the control map on hardware before adding recording menus.
2. **Real recorder:** explicit MIDI input/output, count-in, four-bar takes,
   note durations, sustain, replace/overdub and undo. Verify a keyboard performance
   against captured outgoing MIDI, including notes crossing the loop boundary.
3. **Complete musical workflow:** project save/load, part copy, song entries with
   repeat counts and masks, and reversible quantize/transpose. Demonstrate making
   an intro, verse and chorus without using the computer UI.
4. **Fire as an instrument:** release/timestamp support, NOTE/DRUM input and a
   focused STEP editor. External MIDI clock sync follows as a separately tested
   timing feature.

Before calling it functional, exercise long-held and repeated notes, sustain at
stop, muted tracks sharing channels, undo during playback, slow OLED rendering,
MIDI output loss and shutdown. Use deterministic engine tests for musical
boundaries and hardware checks for controls, readability, responsiveness and
measured timing. Keep the first demo focused on recording and performing eight
tracks; extend the framework only where an actual second application benefits.
