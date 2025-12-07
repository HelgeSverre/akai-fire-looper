"""
Main sequencer engine for the Circuit Tracks-inspired MIDI sequencer.
Coordinates timing, MIDI output, and track playback.
"""

import time
import threading
from typing import List, Dict, Optional, Callable
from enum import Enum

from core.track import Track
from core.scene import Scene
from core.timing import TimingEngine, QuantizationMode
from core.midi_manager import MidiManager
from core.pattern import Pattern, PlayOrder


class TransportState(Enum):
    """Transport states for the sequencer."""

    STOPPED = "STOPPED"
    PLAYING = "PLAYING"
    RECORDING = "RECORDING"


class Sequencer:
    """
    Main sequencer engine that coordinates all components.
    Manages 4 MIDI tracks with pattern playback and recording.
    """

    def __init__(self):
        # Core components
        self.timing = TimingEngine(bpm=120.0)
        self.midi = MidiManager()

        # Track system (4 tracks as per Circuit Tracks)
        self.tracks = self._create_default_tracks()
        self.current_track = 0  # Selected track (0-3)

        # Scene system (16 scenes for live performance)
        self.scenes = [Scene(name=f"Scene {i+1}") for i in range(16)]
        self.current_scene = 0

        # Transport state
        self.transport_state = TransportState.STOPPED
        self.recording_track = None  # Track being recorded to
        self.recording_quantize_start = True  # Quantize recording start

        # Pattern chain management
        self.pattern_chain_positions = [0] * 4  # Current position in chain per track
        self.pattern_chain_step_counts = [0] * 4  # Steps played in current pattern

        # Per-track step positions (for play_order and start/end point support)
        self.track_step_positions = [
            0
        ] * 4  # Current step within pattern for each track

        # Queue system for beat-synced switching
        self.queued_scene: Optional[int] = (
            None  # Scene to switch to at pattern boundary
        )
        self.queued_patterns: Dict[int, int] = {}  # track_index -> pattern_index

        # Note scheduling for precise timing
        self.scheduled_notes = []  # List of (time, channel, note, velocity, duration)
        self.active_notes = {}  # Track note-off timing

        # Tied notes tracking (for tie_forward/legato support)
        # Key: (channel, note), Value: True if tied from previous step
        self.tied_notes: Dict[tuple, bool] = {}

        # Callbacks
        self.step_callbacks = []
        self.transport_callbacks = []

        # Thread safety
        self.lock = threading.Lock()

        # Set up timing callbacks
        self.timing.add_step_callback(self._on_step)

    def _create_default_tracks(self) -> List[Track]:
        """Create default track configuration."""
        track_configs = [
            ("Drums", (255, 0, 0), 10),  # Red, Channel 10 (GM Drums)
            ("Bass", (0, 255, 0), 1),  # Green, Channel 1
            ("Lead", (0, 0, 255), 2),  # Blue, Channel 2
            ("Pad", (255, 255, 0), 3),  # Yellow, Channel 3
        ]

        tracks = []
        for i, (name, color, channel) in enumerate(track_configs):
            track = Track(name=name, color=color, midi_channel=channel)
            tracks.append(track)

        return tracks

    def get_track(self, track_index: int) -> Track:
        """Get a track by index."""
        if 0 <= track_index < len(self.tracks):
            return self.tracks[track_index]
        return Track()  # Return empty track for invalid index

    def set_current_track(self, track_index: int):
        """Set the currently selected track."""
        if 0 <= track_index < len(self.tracks):
            self.current_track = track_index

    def get_current_track(self) -> Track:
        """Get the currently selected track."""
        return self.get_track(self.current_track)

    def play(self):
        """Start playback."""
        with self.lock:
            if self.transport_state == TransportState.STOPPED:
                self.transport_state = TransportState.PLAYING
                self.timing.start_playback()
                self._trigger_transport_callbacks()
                print("Sequencer: Started playback")

    def stop(self):
        """Stop playback and recording."""
        with self.lock:
            if self.transport_state != TransportState.STOPPED:
                # Stop timing engine
                self.timing.stop_playback()

                # Send all notes off
                self.midi.send_all_notes_off()

                # Clear active notes
                self.active_notes.clear()

                # Reset transport state
                self.transport_state = TransportState.STOPPED
                self.recording_track = None

                # Reset pattern chain positions
                self.pattern_chain_positions = [0] * 4
                self.pattern_chain_step_counts = [0] * 4

                # Reset track step positions
                self.track_step_positions = [0] * 4

                # Clear tied notes
                self.tied_notes.clear()

                # Reset ping-pong directions for all patterns
                for track in self.tracks:
                    for pattern in track.patterns:
                        pattern.reset_ping_pong()

                self._trigger_transport_callbacks()
                print("Sequencer: Stopped")

    def record(self, track_index: Optional[int] = None):
        """Start recording on a specific track."""
        if track_index is None:
            track_index = self.current_track

        with self.lock:
            if 0 <= track_index < len(self.tracks):
                self.recording_track = track_index

                if self.transport_state == TransportState.STOPPED:
                    self.transport_state = TransportState.RECORDING
                    self.timing.start_playback()
                else:
                    self.transport_state = TransportState.RECORDING

                self._trigger_transport_callbacks()
                print(f"Sequencer: Recording to track {track_index + 1}")

    def _on_step(self, step: int):
        """Called by timing engine on each step."""
        if self.transport_state == TransportState.STOPPED:
            return

        try:
            with self.lock:
                # Process queued changes at pattern boundary (step 0)
                if step == 0:
                    self._process_queued_changes()

                # Process each track
                for track_idx, track in enumerate(self.tracks):
                    if not track.enabled or track.muted:
                        continue

                    # Get current pattern for this track
                    current_pattern = self._get_current_pattern_for_track(
                        track_idx, step
                    )
                    if not current_pattern:
                        continue

                    # Get the step within the pattern using pattern's play_order
                    pattern_step = self.track_step_positions[track_idx]

                    # Initialize step position on first step
                    if step == 0 and self.pattern_chain_step_counts[track_idx] == 0:
                        pattern_step = current_pattern.get_first_step()
                        self.track_step_positions[track_idx] = pattern_step

                    # Ensure step is within valid range
                    start = current_pattern.start_point
                    end = current_pattern.get_effective_end_point()
                    if pattern_step < start or pattern_step > end:
                        pattern_step = current_pattern.get_first_step()
                        self.track_step_positions[track_idx] = pattern_step

                    step_data = current_pattern.get_step(pattern_step)

                    if step_data.has_notes():
                        self._play_step(
                            track, track_idx, step_data, current_pattern, step
                        )

                    # Advance to next step using pattern's play_order
                    next_step = current_pattern.get_next_step(pattern_step)
                    self.track_step_positions[track_idx] = next_step

                # Update pattern chain positions
                self._update_pattern_chains(step)

                # Process note-offs for expired notes
                self._process_note_offs()

                # Trigger step callbacks
                for callback in self.step_callbacks:
                    callback(step)

        except Exception as e:
            print(f"Error in step callback: {e}")

    def _get_current_pattern_for_track(
        self, track_idx: int, global_step: int
    ) -> Optional[Pattern]:
        """Get the current pattern for a track, handling pattern chains."""
        track = self.tracks[track_idx]

        if track.is_pattern_chained():
            # Handle pattern chain
            chain_pos = self.pattern_chain_positions[track_idx]
            if chain_pos < len(track.pattern_chain):
                pattern_idx = track.pattern_chain[chain_pos]
                return track.get_pattern(pattern_idx)
        else:
            # Single pattern
            return track.get_current_pattern()

        return None

    def _update_pattern_chains(self, step: int):
        """Update pattern chain positions for all tracks."""
        for track_idx, track in enumerate(self.tracks):
            if track.is_pattern_chained():
                # Count steps in current pattern
                chain_pos = self.pattern_chain_positions[track_idx]
                if chain_pos < len(track.pattern_chain):
                    pattern_idx = track.pattern_chain[chain_pos]
                    pattern = track.get_pattern(pattern_idx)

                    self.pattern_chain_step_counts[track_idx] += 1

                    # Check if we've completed the pattern (using playback length)
                    playback_length = pattern.get_playback_length()
                    if self.pattern_chain_step_counts[track_idx] >= playback_length:
                        # Move to next pattern in chain
                        self.pattern_chain_positions[track_idx] += 1
                        self.pattern_chain_step_counts[track_idx] = 0

                        # Reset step position for new pattern
                        next_chain_pos = self.pattern_chain_positions[track_idx]

                        # Loop chain if at end
                        if next_chain_pos >= len(track.pattern_chain):
                            self.pattern_chain_positions[track_idx] = 0
                            next_chain_pos = 0

                        # Reset step position to first step of new pattern
                        if next_chain_pos < len(track.pattern_chain):
                            next_pattern_idx = track.pattern_chain[next_chain_pos]
                            next_pattern = track.get_pattern(next_pattern_idx)
                            next_pattern.reset_ping_pong()
                            self.track_step_positions[track_idx] = (
                                next_pattern.get_first_step()
                            )

    def _process_queued_changes(self):
        """Process queued scene and pattern changes at pattern boundary."""
        # Process queued scene first (overrides individual pattern queues)
        if self.queued_scene is not None:
            scene_index = self.queued_scene
            self.queued_scene = None

            if 0 <= scene_index < len(self.scenes):
                scene = self.scenes[scene_index]
                scene.apply_to_tracks(self.tracks)
                self.current_scene = scene_index

                # Reset pattern chain positions
                self.pattern_chain_positions = [0] * 4
                self.pattern_chain_step_counts = [0] * 4

                # Clear any individual pattern queues (scene takes precedence)
                self.queued_patterns.clear()

                print(f"Applied queued scene {scene_index + 1}: {scene.get_summary()}")

        # Process individual pattern queues
        if self.queued_patterns:
            for track_idx, pattern_idx in self.queued_patterns.items():
                if 0 <= track_idx < len(self.tracks):
                    track = self.tracks[track_idx]
                    if 0 <= pattern_idx < len(track.patterns):
                        track.set_current_pattern(pattern_idx)
                        # Clear chain when switching individual pattern
                        track.pattern_chain = []
                        print(
                            f"Applied queued pattern {pattern_idx + 1} to track {track_idx + 1}"
                        )

            self.queued_patterns.clear()

    def _play_step(
        self, track: Track, track_idx: int, step, pattern: Pattern, global_step: int
    ):
        """Play a single step from a track."""
        # Check probability
        if step.probability < 1.0:
            import random

            if random.random() > step.probability:
                return  # Skip this step due to probability

        # Calculate base step duration with sync_rate modifier
        base_step_duration = (
            self.timing.step_duration * pattern.sync_rate.get_multiplier()
        )

        # Calculate timing with micro-timing and swing
        base_time = time.time()
        micro_offset = (step.micro_timing / 6.0) * (
            base_step_duration * 0.1
        )  # +/- 10% of step
        play_time = base_time + micro_offset

        # Play all notes in the step
        for note, velocity in step.get_notes_with_velocities():
            # Constrain note to track's range
            final_note = track.constrain_note_to_range(note)
            note_key = (track.midi_channel, final_note)

            # Check if this note is tied from previous step
            is_tied = self.tied_notes.get(note_key, False)

            if is_tied:
                # Note is already playing and tied - don't retrigger, just update note-off time
                pass
            else:
                # Send MIDI note on
                self.midi.send_note_on(track.midi_channel, final_note, velocity)

            # Calculate note duration based on gate length
            gate_duration = step.gate_length * base_step_duration

            # If tie_forward is set, extend note through next steps
            if step.tie_forward:
                # Mark this note as tied for next step
                self.tied_notes[note_key] = True
                # Don't schedule note-off yet (will be handled when tie ends)
            else:
                # Clear any existing tie
                if note_key in self.tied_notes:
                    del self.tied_notes[note_key]

                # Schedule note off based on gate length
                note_off_time = play_time + gate_duration
                self.active_notes[note_key] = note_off_time

    def _process_note_offs(self):
        """Process scheduled note-offs."""
        current_time = time.time()
        expired_notes = []

        for note_key, off_time in self.active_notes.items():
            if current_time >= off_time:
                channel, note = note_key
                self.midi.send_note_off(channel, note)
                expired_notes.append(note_key)

        # Remove expired notes
        for note_key in expired_notes:
            del self.active_notes[note_key]

    def record_note(self, track_index: int, note: int, velocity: int):
        """Record a note to the specified track (live recording)."""
        if not (0 <= track_index < len(self.tracks)):
            return

        if self.transport_state != TransportState.RECORDING:
            return

        track = self.tracks[track_index]
        current_pattern = track.get_current_pattern()

        # Get current step position
        current_step, step_position = self.timing.get_current_step_info(
            current_pattern.length
        )

        # Quantize to step if enabled
        if self.timing.quantization != QuantizationMode.OFF and step_position < 0.5:
            # Record to current step
            target_step = current_step
        else:
            # Record to next step
            target_step = (current_step + 1) % current_pattern.length

        # Add note to step
        step_data = current_pattern.get_step(target_step)
        step_data.add_note(note, velocity)

        print(
            f"Recorded note {note} (vel {velocity}) to track {track_index + 1}, step {target_step + 1}"
        )

    def launch_scene(self, scene_index: int, immediate: bool = False):
        """Launch a scene (queue for next pattern boundary, or immediate).

        Args:
            scene_index: Scene to launch (0-15)
            immediate: If True, apply immediately. If False (default), queue for next boundary.
        """
        if not (0 <= scene_index < len(self.scenes)):
            return

        if immediate or self.transport_state == TransportState.STOPPED:
            # Apply immediately
            scene = self.scenes[scene_index]
            scene.apply_to_tracks(self.tracks)
            self.current_scene = scene_index
            self.pattern_chain_positions = [0] * 4
            self.pattern_chain_step_counts = [0] * 4
            print(f"Launched scene {scene_index + 1}: {scene.get_summary()}")
        else:
            # Queue for next pattern boundary
            self.queued_scene = scene_index
            print(
                f"Queued scene {scene_index + 1} (will apply at next pattern boundary)"
            )

    def queue_pattern(self, track_index: int, pattern_index: int):
        """Queue a pattern change for a track at next pattern boundary.

        Args:
            track_index: Track to change (0-3)
            pattern_index: Pattern to switch to (0-7)
        """
        if not (0 <= track_index < len(self.tracks)):
            return
        if not (0 <= pattern_index < 8):
            return

        if self.transport_state == TransportState.STOPPED:
            # Apply immediately when stopped
            self.tracks[track_index].set_current_pattern(pattern_index)
            print(f"Set track {track_index + 1} to pattern {pattern_index + 1}")
        else:
            # Queue for next boundary
            self.queued_patterns[track_index] = pattern_index
            print(f"Queued pattern {pattern_index + 1} for track {track_index + 1}")

    def save_scene(self, scene_index: int, name: Optional[str] = None):
        """Save current track state to a scene."""
        if 0 <= scene_index < len(self.scenes):
            scene = self.scenes[scene_index]
            scene.copy_current_state(self.tracks)

            if name:
                scene.name = name
            else:
                scene.name = f"Scene {scene_index + 1}"

            print(f"Saved scene {scene_index + 1}: {scene.get_summary()}")

    def set_bpm(self, bpm: float):
        """Set the global BPM."""
        self.timing.set_bpm(bpm)

    def get_bpm(self) -> float:
        """Get the current BPM."""
        return self.timing.get_bpm()

    def set_swing(self, swing: float):
        """Set global swing (0.0 to 0.75)."""
        self.timing.set_swing(swing)

    def get_swing(self) -> float:
        """Get current swing amount."""
        return self.timing.get_swing()

    def set_quantization(self, quantization: QuantizationMode):
        """Set quantization mode."""
        self.timing.set_quantization(quantization)

    def add_step_callback(self, callback: Callable[[int], None]):
        """Add a callback for step events."""
        if callback not in self.step_callbacks:
            self.step_callbacks.append(callback)

    def add_transport_callback(self, callback: Callable[[TransportState], None]):
        """Add a callback for transport state changes."""
        if callback not in self.transport_callbacks:
            self.transport_callbacks.append(callback)

    def _trigger_transport_callbacks(self):
        """Trigger all transport callbacks."""
        for callback in self.transport_callbacks:
            try:
                callback(self.transport_state)
            except Exception as e:
                print(f"Error in transport callback: {e}")

    def get_status(self) -> Dict:
        """Get comprehensive sequencer status."""
        timing_info = self.timing.get_timing_info()
        midi_status = self.midi.get_status()

        return {
            "transport_state": self.transport_state.value,
            "current_track": self.current_track + 1,
            "current_scene": self.current_scene + 1,
            "recording_track": (
                self.recording_track + 1 if self.recording_track is not None else None
            ),
            "timing": timing_info,
            "midi": midi_status,
            "tracks": [
                {
                    "name": track.name,
                    "enabled": track.enabled,
                    "soloed": track.soloed,
                    "midi_channel": track.midi_channel,
                    "current_pattern": track.current_pattern + 1,
                    "pattern_chain": [p + 1 for p in track.pattern_chain],
                    "has_content": track.has_content(),
                }
                for track in self.tracks
            ],
        }

    def cleanup(self):
        """Clean up resources."""
        self.stop()
        self.midi.cleanup()
        print("Sequencer cleanup completed")
