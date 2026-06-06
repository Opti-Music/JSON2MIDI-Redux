import sys
import json
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QTabWidget,
    QProgressBar,
    QStatusBar,
    QFrame,
    QGridLayout,
    QHBoxLayout,
)
from PySide6.QtCore import Qt, QThread, Signal, QMutex
from PySide6.QtGui import QFont, QIcon

import mido


class EngineType(Enum):
    PSYCH_NEW = "Psych Engine New"
    PSYCH_LEGACY = "Psych Engine Legacy"
    CODENAME = "Codename Engine"
    VSLICE = "V-Slice"


class Difficulty(Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    ERECT = "erect"
    NIGHTMARE = "nightmare"


@dataclass
class Note:
    time_ms: float
    lane: int
    sustain_ms: float
    is_player: bool
    is_gf: bool = False


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class ConversionThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        chart_path: str,
        output_path: str,
        engine: str,
        bpm_override: float = 0,
        difficulty: str = "normal",
        split_tracks: bool = True,
        meta_path: str = None,
    ):
        super().__init__()
        self.chart_path = chart_path
        self.output_path = output_path
        self.engine = engine
        self.bpm_override = bpm_override
        self.difficulty = difficulty
        self.split_tracks = split_tracks
        self.meta_path = meta_path
        self._mutex = QMutex()
        self._is_running = True

    def stop(self):
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

    def is_running(self):
        self._mutex.lock()
        self._is_running = self._is_running
        self._mutex.unlock()
        return self._is_running

    def run(self):
        try:
            if not self.is_running():
                return

            self.status.emit("Loading chart file...")
            self.progress.emit(10)

            with open(self.chart_path, "r", encoding="utf-8") as f:
                chart_data = json.load(f)

            if not self.is_running():
                return

            self.progress.emit(20)

            if self.engine == EngineType.CODENAME.value:
                self._convert_codename(chart_data)
            elif self.engine == EngineType.VSLICE.value:
                self._convert_vslice(chart_data)
            elif self.engine == EngineType.PSYCH_LEGACY.value:
                self._convert_psych_old(chart_data)
            else:
                self._convert_psych_v1(chart_data)

            if not self.is_running():
                return

            self.progress.emit(100)
            self.finished_signal.emit(True, "Conversion completed successfully!")

        except Exception as e:
            self.finished_signal.emit(False, f"Conversion failed: {str(e)}")

    def _convert_psych_v1(self, chart_data: Dict):
        bpm = self.bpm_override if self.bpm_override > 0 else chart_data.get("bpm", 120)

        if bpm <= 0:
            bpm = 120

        notes = chart_data.get("notes", [])

        if not notes:
            raise ValueError("No note sections found in chart file")

        self._create_midi_from_psych_notes(notes, bpm)

    def _convert_psych_old(self, chart_data: Dict):
        song_data = chart_data.get("song", {})
        bpm = self.bpm_override if self.bpm_override > 0 else song_data.get("bpm", 120)

        if bpm <= 0:
            bpm = 120

        notes = song_data.get("notes", [])

        if not notes:
            raise ValueError("No note sections found in chart file")

        self._create_midi_from_psych_notes(notes, bpm)

    def _convert_codename(self, chart_data: Dict):
        bpm = self.bpm_override
        if bpm <= 0:
            if self.meta_path and os.path.exists(self.meta_path):
                try:
                    with open(self.meta_path, "r") as f:
                        meta_data = json.load(f)
                        bpm = meta_data.get("bpm", 120)
                except:
                    bpm = 120
            else:
                chart_dir = os.path.dirname(self.chart_path)
                meta_path = os.path.join(chart_dir, "meta.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r") as f:
                            meta_data = json.load(f)
                            bpm = meta_data.get("bpm", 120)
                    except:
                        bpm = 120
                else:
                    bpm = 120

        player_notes = []
        opponent_notes = []
        gf_notes = []

        strumlines = chart_data.get("strumLines", [])

        if not strumlines:
            raise ValueError("No strum lines found in chart file")

        for strumline in strumlines:
            position = strumline.get("position", "")
            notes_data = strumline.get("notes", [])

            for note in notes_data:
                time_ms = note.get("time", 0)
                lane = note.get("id", 0)
                sustain = note.get("sLen", 0)

                if position == "boyfriend":
                    player_notes.append((time_ms, lane, sustain))
                elif position == "dad":
                    opponent_notes.append((time_ms, lane, sustain))
                elif position == "girlfriend":
                    gf_notes.append((time_ms, lane, sustain))

        self._create_midi_from_notes(player_notes, opponent_notes, gf_notes, bpm)

    def _convert_vslice(self, chart_data: Dict):
        bpm = self.bpm_override
        if bpm <= 0:
            if self.meta_path and os.path.exists(self.meta_path):
                try:
                    with open(self.meta_path, "r") as f:
                        metadata = json.load(f)
                        time_changes = metadata.get("timeChanges", [])
                        if time_changes:
                            bpm = time_changes[0].get("bpm", 120)
                        else:
                            bpm = 120
                except:
                    bpm = 120
            else:
                chart_dir = os.path.dirname(self.chart_path)
                base_name = os.path.splitext(os.path.basename(self.chart_path))[0]
                base_name = base_name.replace("-chart", "")
                metadata_path = os.path.join(chart_dir, f"{base_name}-metadata.json")

                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                            time_changes = metadata.get("timeChanges", [])
                            if time_changes:
                                bpm = time_changes[0].get("bpm", 120)
                            else:
                                bpm = 120
                    except:
                        bpm = 120
                else:
                    bpm = 120

        notes_data = chart_data.get("notes", {})

        available_diffs = list(notes_data.keys())
        if self.difficulty not in available_diffs:
            raise ValueError(
                f"Difficulty '{self.difficulty}' not found. Available: {', '.join(available_diffs)}"
            )

        notes_list = notes_data.get(self.difficulty, [])

        if not notes_list:
            raise ValueError(f"No notes found for difficulty: {self.difficulty}")

        player_notes = []
        opponent_notes = []

        for note in notes_list:
            time_ms = note.get("t", 0)
            lane = note.get("d", 0)
            sustain = note.get("l", 0)

            if lane < 4:
                player_notes.append((time_ms, lane, sustain))
            else:
                opponent_notes.append((time_ms, lane - 4, sustain))

        self._create_midi_from_notes(player_notes, opponent_notes, [], bpm)

    def _create_midi_from_psych_notes(self, sections: List[Dict], bpm: float):
        player_notes = []
        opponent_notes = []
        gf_notes = []

        current_must_hit = True

        for section_idx, section in enumerate(sections):
            if not self.is_running():
                return

            if not isinstance(section, dict):
                continue

            must_hit = section.get("mustHitSection", current_must_hit)
            current_must_hit = must_hit

            section_notes = section.get("sectionNotes", [])
            for note in section_notes:
                if len(note) < 2:
                    continue

                time_ms = float(note[0])
                lane = int(note[1])
                sustain = float(note[2]) if len(note) > 2 else 0
                note_type = note[3] if len(note) > 3 else ""

                is_gf = note_type == "GF Sing"

                if is_gf:
                    if 0 <= lane <= 7:
                        gf_notes.append((time_ms, lane, sustain))
                    else:
                        print(f"Warning: GF note with invalid lane {lane} ignored")
                elif must_hit:
                    if lane < 4:
                        player_notes.append((time_ms, lane, sustain))
                    else:
                        opponent_notes.append((time_ms, lane - 4, sustain))
                else:
                    if lane < 4:
                        opponent_notes.append((time_ms, lane, sustain))
                    else:
                        player_notes.append((time_ms, lane - 4, sustain))

        self._create_midi_from_notes(player_notes, opponent_notes, gf_notes, bpm)

    def _create_midi_from_notes(
        self,
        player_notes: List,
        opponent_notes: List,
        gf_notes: List,
        bpm: float,
    ):
        if not self.is_running():
            return

        if bpm <= 0:
            bpm = 120

        if not player_notes and not opponent_notes and not gf_notes:
            raise ValueError("No notes found in chart file")

        self.status.emit("Creating MIDI file...")
        self.progress.emit(60)

        midi = mido.MidiFile(ticks_per_beat=480)

        tempo_track = mido.MidiTrack()
        midi.tracks.append(tempo_track)
        tempo_track.append(mido.MetaMessage("track_name", name="Tempo", time=0))
        tempo = mido.bpm2tempo(bpm)
        tempo_track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

        if self.split_tracks:
            dad_track = mido.MidiTrack()
            bf_track = mido.MidiTrack()
            gf_track = mido.MidiTrack()

            midi.tracks.extend([dad_track, bf_track, gf_track])

            dad_track.append(mido.MetaMessage("track_name", name="Dad", time=0))
            bf_track.append(mido.MetaMessage("track_name", name="Boyfriend", time=0))
            gf_track.append(mido.MetaMessage("track_name", name="Girlfriend", time=0))
        else:
            main_track = mido.MidiTrack()
            midi.tracks.append(main_track)
            main_track.append(mido.MetaMessage("track_name", name="All Notes", time=0))

        base_note = 60

        thirty_secondth_ms = (60000 / bpm) / 8
        min_note_duration_ms = max(10, thirty_secondth_ms)

        note_groups = {"bf": {}, "dad": {}, "gf": {}}

        def add_note_to_group(track, note_num, start_ms, end_ms):
            if note_num not in note_groups[track]:
                note_groups[track][note_num] = []
            note_groups[track][note_num].append((start_ms, end_ms))

        for time_ms, lane, sustain in player_notes:
            if 0 <= lane <= 3:
                midi_note = base_note + lane
                end_ms = time_ms + max(sustain, min_note_duration_ms)
                add_note_to_group("bf", midi_note, time_ms, end_ms)

        for time_ms, lane, sustain in opponent_notes:
            if 0 <= lane <= 3:
                midi_note = base_note + lane + 4
                end_ms = time_ms + max(sustain, min_note_duration_ms)
                add_note_to_group("dad", midi_note, time_ms, end_ms)

        for time_ms, lane, sustain in gf_notes:
            if 0 <= lane <= 3:
                midi_note = base_note + 12 + lane
                end_ms = time_ms + max(sustain, min_note_duration_ms)
                add_note_to_group("gf", midi_note, time_ms, end_ms)
            elif 4 <= lane <= 7:
                midi_note = base_note + 16 + (lane - 4)
                end_ms = time_ms + max(sustain, min_note_duration_ms)
                add_note_to_group("gf", midi_note, time_ms, end_ms)

        if not self.is_running():
            return

        self.progress.emit(75)

        all_events = []

        for track_name, notes_dict in note_groups.items():
            for note_num, intervals in notes_dict.items():
                if not intervals:
                    continue

                intervals.sort(key=lambda x: x[0])

                merged = []
                current_start, current_end = intervals[0]

                for start, end in intervals[1:]:
                    if start <= current_end + 5:
                        current_end = max(current_end, end)
                    else:
                        merged.append((current_start, current_end))
                        current_start, current_end = start, end

                merged.append((current_start, current_end))

                for start_ms, end_ms in merged:
                    all_events.append((start_ms, "note_on", note_num, 100, track_name))
                    all_events.append((end_ms, "note_off", note_num, 0, track_name))

        if not self.is_running():
            return

        self.progress.emit(85)
        self.status.emit("Writing MIDI events...")

        ticks_per_beat = midi.ticks_per_beat
        ticks_per_ms = (ticks_per_beat * (bpm / 60.0)) / 1000.0

        if ticks_per_ms > 1000:
            ticks_per_ms = 1000

        if self.split_tracks:
            track_events = {"dad": [], "bf": [], "gf": []}

            for time_ms, ev_type, note, vel, source in all_events:
                if not self.is_running():
                    return
                tick = int(round(time_ms * ticks_per_ms))
                if tick > 2**31 - 1:
                    tick = 2**31 - 1
                msg = mido.Message(ev_type, note=note, velocity=vel, time=0)

                if source in track_events:
                    track_events[source].append((tick, msg))

            self._write_track_events(dad_track, track_events["dad"])
            self._write_track_events(bf_track, track_events["bf"])
            self._write_track_events(gf_track, track_events["gf"])
        else:
            track_events = []
            for time_ms, ev_type, note, vel, _ in all_events:
                if not self.is_running():
                    return
                tick = int(round(time_ms * ticks_per_ms))
                if tick > 2**31 - 1:
                    tick = 2**31 - 1
                track_events.append(
                    (tick, mido.Message(ev_type, note=note, velocity=vel, time=0))
                )
            self._write_track_events(main_track, track_events)

        self.status.emit("Saving MIDI file...")
        self.progress.emit(95)

        midi.save(self.output_path)

    def _write_track_events(
        self, track: mido.MidiTrack, events: List[Tuple[int, mido.Message]]
    ):
        if not events:
            return

        events.sort(key=lambda x: (x[0], 0 if x[1].type == "note_off" else 1))
        current_tick = 0

        for tick, msg in events:
            delta_ticks = tick - current_tick
            if delta_ticks < 0:
                delta_ticks = 0
            elif delta_ticks > 2**31 - 1:
                delta_ticks = 2**31 - 1

            msg.time = delta_ticks
            track.append(msg)
            current_tick = tick


class JSON2MIDI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.chart_path = ""
        self.output_path = ""
        self.meta_path = ""
        self.conversion_thread = None

        self.init_ui()
        self.apply_style()

    def init_ui(self):
        self.setFixedSize(800, 650)
        self.center()

        convert_icon_path = resource_path("icons/convert.png")
        browse_icon_path = resource_path("icons/browse.png")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        title_label = QLabel("JSON2MIDI")
        title_font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        main_ui = QWidget()
        main_ui_layout = QVBoxLayout(main_ui)

        file_group = QGroupBox("File Selection")
        file_layout = QGridLayout(file_group)

        file_layout.addWidget(QLabel("Chart File:"), 0, 0)
        self.chart_file_label = QLabel("No file selected")
        self.chart_file_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        file_layout.addWidget(self.chart_file_label, 0, 1)
        self.browse_chart_btn = QPushButton("Browse")

        if os.path.exists(browse_icon_path):
            self.browse_chart_btn.setIcon(QIcon(browse_icon_path))

        self.browse_chart_btn.clicked.connect(self.browse_chart)
        file_layout.addWidget(self.browse_chart_btn, 0, 2)

        self.meta_group = QWidget()
        meta_layout = QHBoxLayout(self.meta_group)
        meta_layout.setContentsMargins(0, 0, 0, 0)

        self.meta_label = QLabel("Metadata File:")
        self.meta_file_label = QLabel("No file selected")
        self.meta_file_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        self.meta_file_label.setStyleSheet("color: #888888;")
        self.browse_meta_btn = QPushButton("Browse")

        if os.path.exists(browse_icon_path):
            self.browse_meta_btn.setIcon(QIcon(browse_icon_path))

        self.browse_meta_btn.clicked.connect(self.browse_metadata)

        meta_layout.addWidget(self.meta_label)
        meta_layout.addWidget(self.meta_file_label)
        meta_layout.addWidget(self.browse_meta_btn)

        file_layout.addWidget(self.meta_group, 1, 0, 1, 3)
        self.meta_group.setVisible(False)

        file_layout.addWidget(QLabel("Output MIDI:"), 2, 0)
        self.output_file_label = QLabel("No file selected")
        self.output_file_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        file_layout.addWidget(self.output_file_label, 2, 1)
        self.browse_output_btn = QPushButton("Browse")

        if os.path.exists(browse_icon_path):
            self.browse_output_btn.setIcon(QIcon(browse_icon_path))

        self.browse_output_btn.clicked.connect(self.browse_output)
        file_layout.addWidget(self.browse_output_btn, 2, 2)

        main_ui_layout.addWidget(file_group)

        settings_group = QGroupBox("Conversion Settings")
        settings_layout = QGridLayout(settings_group)

        settings_layout.addWidget(QLabel("Engine Format:"), 0, 0)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems([e.value for e in EngineType])
        self.engine_combo.currentTextChanged.connect(self.on_engine_changed)
        settings_layout.addWidget(self.engine_combo, 0, 1)

        settings_layout.addWidget(QLabel("Difficulty (only V-Slice):"), 1, 0)
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems([d.value for d in Difficulty])
        self.difficulty_combo.setEnabled(False)
        settings_layout.addWidget(self.difficulty_combo, 1, 1)

        settings_layout.addWidget(QLabel("BPM (0 = auto):"), 3, 0)
        self.bpm_spin = QDoubleSpinBox()
        self.bpm_spin.setRange(0, 500)
        self.bpm_spin.setValue(0)
        self.bpm_spin.setSingleStep(1)
        self.bpm_spin.setSuffix(" BPM")
        settings_layout.addWidget(self.bpm_spin, 3, 1)

        self.split_tracks_checkbox = QCheckBox("Split tracks")
        self.split_tracks_checkbox.setChecked(True)
        settings_layout.addWidget(self.split_tracks_checkbox, 4, 0, 1, 2)

        main_ui_layout.addWidget(settings_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_ui_layout.addWidget(self.progress_bar)

        self.convert_btn = QPushButton("Convert to MIDI")
        self.convert_btn.setMinimumHeight(40)

        if os.path.exists(convert_icon_path):
            self.convert_btn.setIcon(QIcon(convert_icon_path))

        self.convert_btn.clicked.connect(self.start_conversion)
        main_ui_layout.addWidget(self.convert_btn)

        main_ui_layout.addStretch()

        tabs.addTab(main_ui, "Main")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.convert_btn.setEnabled(False)

    def center(self):
        frame_geo = self.frameGeometry()
        screen = QApplication.primaryScreen()
        available_geo = screen.availableGeometry()
        center_point = available_geo.center()
        frame_geo.moveCenter(center_point)
        self.move(frame_geo.topLeft())

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4a4a4a;
                border: 1px solid #666666;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #888888;
            }
            QComboBox {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                selection-background-color: #5a5a5a;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                background-color: #4a4a4a;
                border: 1px solid #666666;
                border-top-right-radius: 3px;
                width: 20px;
            }
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
                background-color: #5a5a5a;
            }
            QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {
                background-color: #3a3a3a;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                background-color: #4a4a4a;
                border: 1px solid #666666;
                border-bottom-right-radius: 3px;
                width: 20px;
            }
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #5a5a5a;
            }
            QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
                background-color: #3a3a3a;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 5px solid #ffffff;
                margin-bottom: 2px;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-top: 2px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #555555;
                background-color: #3a3a3a;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
            QLabel {
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #3a3a3a;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #4a4a4a;
            }
            QTabBar::tab:hover {
                background-color: #4a4a4a;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
                border-radius: 3px;
            }
            QFrame[frameShape="4"] {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
            }
        """)

    def on_engine_changed(self, engine: str):
        if engine == EngineType.VSLICE.value:
            self.meta_label.setText("Metadata File (V-Slice):")
            self.meta_group.setVisible(True)
            self.difficulty_combo.setEnabled(True)
        elif engine == EngineType.CODENAME.value:
            self.meta_label.setText("Meta File (Codename):")
            self.meta_group.setVisible(True)
            self.difficulty_combo.setEnabled(False)
        else:
            self.meta_group.setVisible(False)
            self.difficulty_combo.setEnabled(False)

        self.update_convert_button()

    def detect_engine(self, chart_data: Dict) -> str:
        if "version" in chart_data:
            return EngineType.VSLICE.value

        if "codenameChart" in chart_data:
            return EngineType.CODENAME.value

        if "format" in chart_data and chart_data["format"] == "psych_v1":
            return EngineType.PSYCH_NEW.value

        return EngineType.PSYCH_LEGACY.value

    def browse_chart(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Chart File", "", "JSON files (*.json);;All files (*.*)"
        )
        if file_path:
            self.chart_path = file_path
            self.chart_file_label.setText(os.path.basename(file_path))

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    chart_data = json.load(f)

                detected_engine = self.detect_engine(chart_data)

                index = self.engine_combo.findText(detected_engine)
                if index >= 0:
                    self.engine_combo.setCurrentIndex(index)
                    self.status_bar.showMessage(f"Detected engine: {detected_engine}")

                    if detected_engine == EngineType.VSLICE.value:
                        chart_dir = os.path.dirname(file_path)
                        base_name = os.path.splitext(os.path.basename(file_path))[0]
                        base_name = base_name.replace("-chart", "")
                        output_meta = os.path.join(
                            chart_dir, f"{base_name}-metadata.json"
                        )
                        if os.path.exists(output_meta):
                            self.meta_path = output_meta
                            self.meta_file_label.setText(os.path.basename(output_meta))
                            self.meta_file_label.setStyleSheet("color: #ffffff;")
                            self.status_bar.showMessage(
                                f"Auto-detected metadata file: {os.path.basename(output_meta)}"
                            )
                    elif detected_engine == EngineType.CODENAME.value:
                        chart_dir = os.path.dirname(file_path)
                        output_meta = os.path.join(chart_dir, "meta.json")
                        if os.path.exists(output_meta):
                            self.meta_path = output_meta
                            self.meta_file_label.setText(os.path.basename(output_meta))
                            self.meta_file_label.setStyleSheet("color: #ffffff;")
                            self.status_bar.showMessage(
                                f"Auto-detected meta file: {os.path.basename(output_meta)}"
                            )

            except Exception as e:
                self.status_bar.showMessage(f"Error reading chart: {str(e)}")

            self.update_convert_button()

    def browse_metadata(self):
        engine = self.engine_combo.currentText()

        if engine == EngineType.VSLICE.value:
            file_types = "Metadata JSON files (*-metadata.json);;JSON files (*.json);;All files (*.*)"
            dialog_title = "Select V-Slice Metadata File"
        elif engine == EngineType.CODENAME.value:
            file_types = (
                "Meta JSON files (meta.json);;JSON files (*.json);;All files (*.*)"
            )
            dialog_title = "Select Codename Meta File"
        else:
            file_types = "JSON files (*.json);;All files (*.*)"
            dialog_title = "Select Metadata File"

        file_path, _ = QFileDialog.getOpenFileName(self, dialog_title, "", file_types)
        if file_path:
            self.meta_path = file_path
            self.meta_file_label.setText(os.path.basename(file_path))
            self.meta_file_label.setStyleSheet("color: #ffffff;")
            self.update_convert_button()

    def browse_output(self):
        if self.chart_path:
            base_name = os.path.basename(self.chart_path)
            file_name = os.path.splitext(base_name)[0]
            output_name = f"{file_name}.mid"
        else:
            output_name = "output.mid"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save MIDI As", output_name, "MIDI files (*.mid);;All files (*.*)"
        )
        if file_path:
            if not file_path.endswith(".mid"):
                file_path += ".mid"
            self.output_path = file_path
            self.output_file_label.setText(os.path.basename(file_path))
            self.update_convert_button()

    def update_convert_button(self):
        has_chart = bool(self.chart_path)
        has_output = bool(self.output_path)
        engine = self.engine_combo.currentText()
        
        needs_meta = engine in [EngineType.VSLICE.value, EngineType.CODENAME.value]
        has_meta = bool(self.meta_path) if needs_meta else True

        self.convert_btn.setEnabled(has_chart and has_output and has_meta)

    def start_conversion(self):
        if self.conversion_thread and self.conversion_thread.isRunning():
            return

        self.convert_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.conversion_thread = ConversionThread(
            chart_path=self.chart_path,
            output_path=self.output_path,
            engine=self.engine_combo.currentText(),
            bpm_override=self.bpm_spin.value(),
            difficulty=self.difficulty_combo.currentText(),
            split_tracks=self.split_tracks_checkbox.isChecked(),
            meta_path=self.meta_path if self.meta_group.isVisible() else None,
        )

        self.conversion_thread.progress.connect(self.progress_bar.setValue)
        self.conversion_thread.status.connect(self.status_bar.showMessage)
        self.conversion_thread.finished_signal.connect(self.conversion_finished)
        self.conversion_thread.start()

    def conversion_finished(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        self.update_convert_button()

        if success:
            QMessageBox.information(self, "Success", message)
            self.status_bar.showMessage("Conversion successful")
        else:
            QMessageBox.critical(self, "Error", message)
            self.status_bar.showMessage("Conversion failed")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JSON2MIDI()
    window.show()
    sys.exit(app.exec())
