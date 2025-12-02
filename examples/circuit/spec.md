# Circuit Tracks-Inspired MIDI Sequencer - Specification

## Project Overview

A professional 4-track **MIDI-only sequencer** for the AKAI Fire controller, inspired by the Novation Circuit Tracks workflow. This is a **pure MIDI orchestration system** designed to control external hardware synthesizers, drum machines, and DAWs through MIDI messages. The AKAI Fire serves as a dedicated hardware controller interface, providing immediate tactile control over MIDI sequences with real-time visual feedback on the controller's pads and OLED screen.

**Key Distinction**: This system handles **MIDI data only** - no audio processing, mixing, or sound generation. All audio is produced by external MIDI devices that receive the sequenced MIDI data from this controller.

## Design Philosophy

### Core Principles
- **Remove Friction**: Every design decision prioritizes removing barriers between musical ideas and their realization
- **Instrument-Like Feel**: Tactile, physical interface that feels like playing an instrument, not programming a computer
- **Screen-Minimal Workflow**: Hardware provides immediate feedback, LCD screen provides context and precision
- **Performance-First**: Designed for live manipulation and real-time creativity
- **MIDI-Only Architecture**: Pure MIDI orchestration system - no audio processing whatsoever
- **Hardware Synth Workflow**: Optimized for controlling external hardware synthesizers and drum machines
- **Computer as Hub**: Python script orchestrates MIDI I/O while Fire provides the tactile interface

### User Experience Goals
- **5-Second Rule**: Users can create a basic pattern within 5 seconds
- **One-Handed Operation** for most functions during performance
- **Eyes-Free Operation** supported by consistent visual patterns
- **Muscle Memory Friendly** - spatial relationships remain consistent
- **Flow State Preservation** - no cognitive load on technical operation

---

## Hardware Architecture

### AKAI Fire Grid Layout (4 rows × 16 columns = 64 pads)

```
ROW 1: [16-Step Sequencer Display]
       ● ○ ● ○ ● ○ ● ○ ● ○ ● ○ ● ○ ● ○
       Current step=white, Active steps=track color, Beat markers=dim

ROW 2: [Track & Pattern Control]
       T1 T2 T3 T4 | P1 P2 P3 P4 P5 P6 P7 P8 | □ □ □ □
       Tracks 1-4   | Patterns 1-8 per track  | Reserved

ROWS 3-4: [Context-Sensitive Input Area - 32 pads]
          Mode-dependent: Keyboard/Mixer/Velocity/Gate/etc.
```

### Hardware Button Mapping

#### Transport Controls
- **PLAY**: Start/stop playback (LED: off=stopped, green=playing)
- **REC**: Global record arm/disarm (LED: off=disarmed, red=recording, yellow=armed)
- **STOP**: Panic button - stop all playback and recording immediately

#### Navigation & Modes
- **BROWSER**: Cycle through main modes (Note → Mixer → Pattern → Settings → Note)
- **GRID LEFT/RIGHT**: Page through steps 1-16 / 17-32 for 32-step patterns
- **SHIFT**: Modifier for advanced functions (Step Edit, Pattern Copy, etc.)

#### Real-Time Control
- **Volume Encoder**: BPM control (30-300 BPM, velocity-sensitive)
- **Filter Encoder**: Global swing (0-75%)
- **Pan Encoder**: Quantization settings (Off, 1/4, 1/8, 1/16, 1/32)
- **SELECT**: Confirm selections, enter menus, step edit mode

---

## MIDI-Only Architecture

### System Flow
```
AKAI Fire ← USB → Python Script ← MIDI → Hardware Synths
    ↑                    ↑                      ↑
 Visual UI         MIDI Orchestration      Sound Generation
 Real-time         Pattern Sequencing      Audio Output
 Feedback          Timing Control          Musical Output
```

### Hardware Synth Workflow
This system is designed specifically for controlling **external hardware synthesizers** via MIDI:

1. **Computer as MIDI Hub**: Python script handles all MIDI I/O, timing, and sequencing
2. **Fire as Controller**: Provides tactile interface with visual feedback on pads and screen  
3. **External Synths**: Receive MIDI data and generate audio (Moog, Prophet, Elektron, etc.)
4. **No Audio Processing**: Zero audio handling - pure MIDI command and control

### Typical Setup Example
```
AKAI Fire → Computer (Python) → MIDI Interface → Hardware Setup:
                                     ├─ Channel 1: Moog Bass (Track 1 - Red)
                                     ├─ Channel 2: Prophet Lead (Track 2 - Green)  
                                     ├─ Channel 10: Elektron Drums (Track 3 - Blue)
                                     └─ Channel 3: Juno Pads (Track 4 - Yellow)
```

### MIDI Data Types Handled
- **Note On/Off**: Pattern playback with velocity and timing
- **Control Change (CC)**: Real-time parameter control via Mixer Mode
- **Clock/Transport**: Master timing for hardware synchronization

note: we dont care about program change or sysex messages for now.
---

## Track System

### 4 Independent MIDI Tracks

```
Track 1: MIDI Channel 1-16 (configurable) - Color: Red (#FF0000)
Track 2: MIDI Channel 1-16 (configurable) - Color: Green (#00FF00)
Track 3: MIDI Channel 1-16 (configurable) - Color: Blue (#0000FF)
Track 4: MIDI Channel 1-16 (configurable) - Color: Yellow (#FFFF00)
```

### Track Properties
- **MIDI Channel**: 1-16, independently configurable  
- **MIDI Port**: Route to different hardware/software synths
- **Pattern Storage**: 8 patterns per track (64 total patterns)
- **Pattern Length**: 1-32 steps per pattern
- **Enable/Disable State**: Independent MIDI output per track
- **Scale Settings**: Per-track scale and root note for input
- **Velocity Curve**: Linear, exponential, logarithmic per track
- **Note Range**: Limit/transpose MIDI note output range
- **CC Assignments**: Assignable MIDI CC mappings per track

### Pattern Organization
- **8 patterns per track** for extensive arrangement possibilities
- **Pattern chaining**: Sequential playback (1→2→3→4) for longer sequences
- **Pattern memory**: Each pattern stores steps, notes, velocities, gates, probabilities
- **Pattern sync**: All tracks synchronized to global timing

---

## Mode System

The same hardware grid transforms completely based on current mode, following Circuit Tracks philosophy.

### 1. Note Mode (Default)
**Purpose**: Primary composition and note input

**Grid Layout**:
- **Row 1**: 16-step sequencer visualization
- **Row 2**: Track selection (T1-T4) + Pattern selection (P1-P8)
- **Rows 3-4**: Scale-based keyboard (2 octaves, root notes highlighted)

**LCD Display**:
```
┌─────────────────────────────────────────────┐
│ Track 2: Green  Ch: 1  PLAYING             │  
├─────────────────────────────────────────────┤
│ Pattern 1-2 (Chain)  BPM: 128  Swing: 25%  │
│ Scale: C Major  Oct: 3  Quant: 1/16        │
│ Note: C3 (60)  Vel: 85  Gate: 75%          │  <- Real-time info
│                                             │
│ [Volume: BPM]  [Pan: Quant]  [Filt: Swing] │
└─────────────────────────────────────────────┘
```

**Controls**:
- **Pads T1-T4**: Select active track
- **Pads P1-P8**: Select pattern for current track
- **Rows 3-4**: Play notes in selected scale
- **Volume Encoder**: BPM adjustment
- **Filter Encoder**: Global swing
- **Pan Encoder**: Quantization setting

### 2. Mixer Mode (Shift + Browser)
**Purpose**: MIDI track control, scene launching, live performance

**Grid Layout**:
- **Row 1**: MIDI activity indicators (brightness = note velocity)
- **Row 2**: Track mute/solo (T1-T4) + Scene triggers (S1-S8)
- **Rows 3-4**: MIDI CC controls for external hardware (32 controllers)

**LCD Display**:
```
┌─────────────────────────────────────────────┐
│ MIXER MODE - MIDI Track Control            │
├─────────────────────────────────────────────┤
│ T1: Muted    T2: Solo    T3: ████    T4: ██ │  <- MIDI activity
│ Scene: 3 Active  Next: 4 Queued            │
│ Ch1: CC7=85  Ch2: CC1=120  Ch10: CC7=64    │  <- MIDI CC values
│                                             │
│ [Vol: CC7]  [Filt: CC74]  [Pan: CC10]      │
└─────────────────────────────────────────────┘
```

**Controls**:
- **Row 1**: Visual MIDI note activity feedback (no audio - pure visual)
- **Pads T1-T4**: Mute/unmute MIDI tracks (stops MIDI output)
- **Pads S1-S8**: Launch scenes (pattern combinations)
- **Rows 3-4**: Send MIDI CC messages to control external hardware parameters

### 3. Pattern Mode (Hold Browser)
**Purpose**: Pattern chaining, arrangement, song structure

**Grid Layout**:
- **Row 1**: Chain visualization (connected patterns highlighted)
- **Row 2**: Track selection + Pattern bank selection
- **Rows 3-4**: All 32 patterns across tracks (8×4 grid)

**LCD Display**:
```
┌─────────────────────────────────────────────┐
│ PATTERN MODE - Song Arrangement             │
├─────────────────────────────────────────────┤
│ Track 1: Pattern Chain 1→2→3→4 (16 bars)   │
│ Track 2: Pattern 5 (4 bars loop)           │
│ Track 3: Pattern Chain 2→6 (8 bars)        │
│ Track 4: Pattern 1 (4 bars loop)           │
│ [Select: Edit]  [Clear: Delete]  [Dup: Copy]│
└─────────────────────────────────────────────┘
```

**Controls**:
- **Sequential pad press**: Create pattern chains (1→2→3→4)
- **Shift + pad**: Clear pattern
- **Duplicate + pad**: Copy pattern
- **Clear + pad**: Delete pattern

### 4. Step Edit Mode (Hold Select + Step)
**Purpose**: Detailed step parameter editing

**Grid Layout**:
- **Row 1**: Current 16 steps (selected step = yellow)
- **Row 2**: Step parameter selection (Velocity, Gate, Probability, Micro-timing)
- **Rows 3-4**: Parameter value adjustment (32 levels of resolution)

**LCD Display**:
```
┌─────────────────────────────────────────────┐
│ Step 5 Edit - Track 2 Green                │
├─────────────────────────────────────────────┤
│ Notes: C3(60), E3(64), G3(67)              │  <- Polyphonic step
│ Velocity: 85/127  Gate: 75%  Prob: 100%    │
│ Micro: +2/6  Duration: 1/16                │
│                                             │
│ [Vel]  [Gate]  [Prob]  [Micro]  [Note+/-]  │
└─────────────────────────────────────────────┘
```

### 5. Settings Mode (Shift + Save)
**Purpose**: MIDI configuration, global settings, system preferences

**LCD Display Navigation**:
```
Settings Menu:
> MIDI Configuration
  Scale Settings  
  System Settings
  Project Settings

MIDI Configuration:
> Track 1: Channel 10 (Drums)
  Track 2: Channel 1 (Bass)
  Track 3: Channel 2 (Lead)  
  Track 4: Channel 3 (Pad)
  MIDI Ports: FL STUDIO FIRE
  Sync Settings: Internal/External
```

**Controls**:
- **Rotary Select**: Navigate menu items
- **SELECT**: Confirm choices
- **Rotary encoders**: Adjust values (channels, ports, etc.)
- **BROWSER**: Exit settings

---

## Visual Feedback System

### Pad Color Language
```
Track Colors:
- Track 1: Red (#FF0000)     - Typically drums/percussion
- Track 2: Green (#00FF00)   - Typically bass/low end  
- Track 3: Blue (#0000FF)    - Typically lead/melody
- Track 4: Yellow (#FFFF00)  - Typically harmony/chords

Brightness Levels:
- Dim (25):    Empty/Available/Inactive
- Medium (75): Has Content/Armed/Selected  
- Bright (127): Currently Playing/Recording/Active

State Colors:
- White (127,127,127): Current playhead position
- Orange (127,64,0):   Armed for recording
- Red (127,0,0):       Currently recording  
- Purple (127,0,127):  Muted track/clip
- Cyan (0,127,127):    Soloed track
```

### Step Sequencer Visualization (Row 1)
```
Current Step Pattern Display:
■ □ ■ ● □ ■ □ ○ ■ □ ■ ● □ ■ □ ○

Legend:
● = Current step (white, bright)
■ = Active step with notes (track color, medium)  
○ = Beat marker (track color, dim)
□ = Empty step (off)
```

### LCD Screen Patterns

#### Header Format (All Modes)
```
┌─────────────────────────────────────────────┐
│ [Mode] [Track Info] [Transport State]      │  <- Inverted header
├─────────────────────────────────────────────┤
```

#### Real-Time Information Display
- **Current playing notes**: Note names and MIDI numbers
- **Parameter values**: Live updates during adjustment
- **MIDI activity**: Channel activity, velocity info
- **Transport state**: BPM, bar position, timing info
- **Mode context**: Available controls and functions

---

## Data Structures

### Core Pattern Storage
```python
@dataclass
class Step:
    notes: List[int]          # MIDI note numbers (polyphonic)
    velocities: List[int]     # Per-note velocities  
    gate_length: float        # 0.0-1.0 (percentage of step)
    probability: float        # 0.0-1.0 (trigger probability)
    micro_timing: int         # -6 to +6 (micro-step offset)
    enabled: bool            # Step on/off

@dataclass  
class Pattern:
    steps: List[Step]         # 16 or 32 steps
    length: int               # Actual pattern length (1-32)
    name: str                # User-definable pattern name
    
@dataclass
class Track:
    name: str                # Track name
    color: Tuple[int,int,int] # RGB color
    midi_channel: int        # 1-16 MIDI channel
    midi_port: str           # MIDI port name
    patterns: List[Pattern]   # 8 patterns per track
    current_pattern: int     # Currently playing pattern
    pattern_chain: List[int] # Pattern chain sequence  
    enabled: bool           # Track MIDI output enabled/disabled
    soloed: bool            # Track solo state (disables other tracks)
    scale: str              # Musical scale for input
    root_note: int          # Root note (0-11)
    octave: int             # Octave offset
    note_range: Tuple[int, int]  # MIDI note range limits (min, max)
    cc_assignments: Dict[str, int]  # CC mappings for hardware control
    
@dataclass
class Scene:
    name: str               # Scene name
    pattern_assignments: Dict[int, int]  # Track -> Pattern mapping
    track_states: Dict[int, bool]       # Track mute states
```

### Global State Management
```python
class SequencerState:
    tracks: List[Track]          # 4 tracks total
    current_track: int           # Selected track (0-3)
    current_mode: Mode           # UI mode
    bpm: float                   # 30.0-300.0
    global_swing: float          # 0.0-0.75
    quantization: str            # "OFF", "1/4", "1/8", "1/16", "1/32"
    transport_state: str         # "STOPPED", "PLAYING", "RECORDING"
    scenes: List[Scene]          # 16 scenes for live performance
    current_scene: int           # Active scene
```

---

## Musical Features

### Scale System (16 Built-in Scales)
```python
SCALES = {
    "MAJOR": [0, 2, 4, 5, 7, 9, 11],
    "NATURAL_MINOR": [0, 2, 3, 5, 7, 8, 10],
    "DORIAN": [0, 2, 3, 5, 7, 9, 10],
    "PHRYGIAN": [0, 1, 3, 5, 7, 8, 10],
    "MIXOLYDIAN": [0, 2, 4, 5, 7, 9, 10],
    "MELODIC_MINOR": [0, 2, 3, 5, 7, 9, 11],
    "HARMONIC_MINOR": [0, 2, 3, 5, 7, 8, 11],
    "BEBOP_DORIAN": [0, 2, 3, 5, 7, 9, 10, 11],
    "BLUES": [0, 3, 5, 6, 7, 10],
    "MINOR_PENTATONIC": [0, 3, 5, 7, 10],
    "HUNGARIAN_MINOR": [0, 2, 3, 6, 7, 8, 11],
    "UKRAINIAN_DORIAN": [0, 2, 3, 6, 7, 9, 10],
    "MARVA": [0, 1, 4, 6, 7, 9, 11],
    "TODI": [0, 1, 3, 6, 7, 8, 11],
    "WHOLE_TONE": [0, 2, 4, 6, 8, 10],
    "CHROMATIC": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
}
```

### Pattern Chaining System
- **Consecutive chaining**: Patterns must be sequential (1→2→3, not 1→3→7)
- **Chain length**: Up to 8 patterns per chain (8×32 = 256 steps maximum)
- **Visual feedback**: Chained patterns light up in sequence
- **Loop points**: Chains can loop or play once

### Scene System
- **16 scenes total**: Accessible in Mixer Mode
- **Scene content**: Stores which pattern is active per track
- **Scene chaining**: Create complete song arrangements
- **Live launching**: Queue scenes for seamless transitions
- **Scene editing**: Real-time pattern assignment to scenes

---

## Implementation Phases

### Phase 1: Core Sequencer (MVP)
**Timeline**: 2-3 weeks
**Features**:
1. Basic 4-track MIDI sequencer
2. Note Mode with scale-based input (C Major only)
3. 16-step patterns with basic step editing
4. Simple MIDI output (fixed channels)
5. Basic transport controls (Play/Stop/Record)
6. LCD display with track info and BPM

**Success Criteria**:
- Can create and play basic 4-track patterns
- MIDI output works with external devices
- Visual feedback shows current step and notes
- Basic recording functionality works

### Phase 2: Mode System & Configuration
**Timeline**: 2-3 weeks  
**Features**:
1. Complete mode system (Note/Mixer/Pattern/Settings)
2. MIDI channel configuration per track
3. Pattern selection and basic pattern management
4. Enhanced LCD displays for all modes
5. Track muting/soloing in Mixer Mode
6. Global swing and quantization controls

**Success Criteria**:
- All 4 modes functional and intuitive
- MIDI channels configurable per track
- Smooth mode transitions with proper visual feedback
- Track mixing works in real-time

### Phase 3: Advanced Pattern Features
**Timeline**: 3-4 weeks
**Features**:
1. Pattern chaining system (1→2→3→4)
2. All 16 musical scales with root note selection
3. Step editing (velocity, gate, probability, micro-timing)
4. 32-step pattern support with paging
5. Pattern copy/paste/clear functions
6. Enhanced step sequencer visualization

**Success Criteria**:
- Pattern chaining creates seamless longer sequences
- Scale system prevents wrong notes and enhances creativity
- Step editing allows detailed parameter control
- 32-step patterns work with proper paging

### Phase 4: Performance & Scene System
**Timeline**: 2-3 weeks
**Features**:
1. Scene system for live performance
2. Scene chaining for song arrangement
3. Real-time pattern launching and queuing
4. Advanced MIDI features (velocity curves, note range limits)
5. Project save/load functionality
6. Performance optimizations and polish

**Success Criteria**:
- Scene system enables fluid live performance
- All patterns and scenes save/load reliably
- Real-time performance is responsive and stable
- System is ready for professional use

---

## Technical Requirements

### Hardware Dependencies
- AKAI Fire MIDI controller
- Computer with USB port
- MIDI output capability (built-in or interface)
- Optional: External MIDI devices for full experience

### Software Dependencies
- Python 3.8+
- python-rtmidi for MIDI I/O
- PIL (Pillow) for screen graphics
- akai_fire library (existing codebase)

### Performance Targets
- **MIDI Timing Jitter**: < 1ms variation in step timing
- **Visual Latency**: < 50ms from input to visual feedback  
- **MIDI Output Precision**: Sub-millisecond accuracy for hardware synths
- **CPU Usage**: < 5% on modern systems during normal operation
- **MIDI Throughput**: Handle 4 simultaneous tracks at 32nd note resolution

### File Structure
```
examples/circuit/
├── main.py                 # Main application entry point
├── spec.md                 # This specification document
├── core/
│   ├── __init__.py
│   ├── sequencer.py        # Main sequencer engine
│   ├── track.py            # Track management
│   ├── pattern.py          # Pattern storage and playback
│   ├── timing.py           # Timing and synchronization
│   ├── midi_manager.py     # MIDI I/O handling
│   └── scales.py           # Musical scale definitions
├── ui/
│   ├── __init__.py
│   ├── mode_manager.py     # UI mode switching
│   ├── screen_manager.py   # LCD display management
│   ├── grid_manager.py     # Pad grid control
│   └── modes/
│       ├── __init__.py
│       ├── note_mode.py    # Note input and composition
│       ├── mixer_mode.py   # Track mixing and scenes
│       ├── pattern_mode.py # Pattern management
│       ├── step_edit_mode.py # Step parameter editing
│       └── settings_mode.py # Configuration and setup
└── tests/
    ├── __init__.py
    ├── test_core.py        # Core functionality tests
    ├── test_ui.py          # UI mode tests
    └── test_integration.py # Full system tests
```

---

## Success Metrics

### Usability Goals
- **5-Second Pattern Creation**: Basic 4-track pattern in under 5 seconds
- **One-Handed Performance**: 90% of live performance functions accessible with one hand
- **Eyes-Free Operation**: Core workflow possible without looking at screen
- **Mode Switching**: < 1 second to switch between any modes
- **Pattern Creation Speed**: Complete 32-step pattern in under 2 minutes

### Musical Goals
- **Sub-Millisecond MIDI Timing**: Professional-grade MIDI timing accuracy
- **Hardware Synth Integration**: Seamless control of external synthesizers
- **Creative Flow**: Interface disappears, focus stays on musical ideas
- **Performance Ready**: Suitable for live hardware performance without preparation
- **Scale System Effectiveness**: 95% reduction in "wrong" notes with scale-aware input
- **Hardware Workflow Optimization**: Streamlined control of multi-synth setups

### Technical Goals
- **Stability**: 8+ hour continuous operation without issues
- **Responsiveness**: All user inputs processed within 50ms
- **MIDI Compatibility**: Works with 99% of MIDI devices and software
- **Resource Efficiency**: Minimal CPU and memory usage
- **Professional Quality**: Suitable for studio and live professional use

---

This specification provides a complete roadmap for building a professional Circuit Tracks-inspired MIDI sequencer that leverages the AKAI Fire's superior display and grid layout while maintaining the intuitive, performance-first workflow that makes the Circuit Tracks so popular with musicians.
