"""
Holoyomi - JP→EN Subtitle Overlay for VTuber Streams
Fixed version with proper subtitle pipeline integration
"""
import sys
import os
import threading
import ffmpeg
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel, QFileDialog, 
    QVBoxLayout, QHBoxLayout, QSlider, QSizePolicy, QMessageBox, QDialog, QCheckBox
)
from PyQt5.QtGui import QLinearGradient, QBrush, QColor, QPainter, QFont
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import QStyle
import vlc
import random

# Import your modules
from config import AUDIO_FILE, CHUNK_DURATION, SAMPLERATE, ASR_MODEL_PATH, USE_TRANSLATION
from audio.audio_file_capture import AudioFileCapture
from asr.jp_asr import JapaneseASR
if USE_TRANSLATION:
    from translate.jp_to_en import JPToENTranslator
else:
    JPToENTranslator = None


class SubtitleSignals(QObject):
    """Signals for thread-safe subtitle updates"""
    update_text = pyqtSignal(str, str)  # jp_text, en_text


class SubtitleOverlay(QLabel):
    def __init__(self, video_widget):
        super().__init__(video_widget)
        self.setText("")
        self.bg_opacity = 0.0
        self.font_size = 26
        self.text_opacity = 1.0
        self.setStyleSheet(self._make_style(font_size=self.font_size, bg_opacity=self.bg_opacity, text_opacity=self.text_opacity))
        self.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        self.setVisible(True)
        self.margin = 0.05
        self._settings_dialog = None
        self._visible = True
        self.installEventFilter(self)

    def _make_style(self, font_size, bg_opacity, text_opacity):
        return f"""
            background: transparent;
            color: rgba(255,255,255,{text_opacity});
            font-family: 'Segoe UI', 'Roboto', Arial, sans-serif;
            font-size: {font_size}px;
            padding: 0px 8px;
            border: none;
            text-align: center;
            text-shadow: 0px 0px 4px #000, 2px 2px 4px #000, -2px 2px 4px #000, 2px -2px 4px #000, -2px -2px 4px #000;
        """

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_start') and event.buttons() & Qt.LeftButton:
            parent = self.parentWidget()
            if parent:
                new_pos = self.mapToParent(event.pos() - self._drag_start + self.pos())
                x = max(0, min(new_pos.x(), parent.width() - self.width()))
                y = max(0, min(new_pos.y(), parent.height() - self.height()))
                self.move(x, y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if hasattr(self, '_drag_start'):
            del self._drag_start
        super().mouseReleaseEvent(event)

    def resize_with_video(self):
        parent = self.parentWidget()
        if parent:
            w, h = parent.width(), parent.height()
            width = int(w * 0.8)
            height = int(h * 0.13)
            x = int((w - width) / 2)
            y = int(h - height - h * self.margin)
            self.setGeometry(x, y, width, height)

    def set_subtitle(self, text):
        self.setText(text)
        self.setVisible(self._visible and bool(text.strip()))

    def show_settings(self):
        if self._settings_dialog is None:
            self._settings_dialog = SubtitleSettingsDialog(self)
        self._settings_dialog.show()

    def set_font_size(self, size):
        self.font_size = size
        self.setStyleSheet(self._make_style(self.font_size, self.bg_opacity, self.text_opacity))

    def set_bg_opacity(self, opacity):
        self.bg_opacity = 0
        self.setStyleSheet(self._make_style(self.font_size, 0, self.text_opacity))

    def set_text_opacity(self, opacity):
        self.text_opacity = opacity
        self.setStyleSheet(self._make_style(self.font_size, self.bg_opacity, self.text_opacity))

    def set_subtitle_visible(self, visible):
        self._visible = visible
        self.setVisible(visible and bool(self.text()))

    def eventFilter(self, obj, event):
        if event.type() == event.Resize:
            self.resize_with_video()
        return super().eventFilter(obj, event)


class SubtitleSettingsDialog(QDialog):
    def __init__(self, overlay):
        super().__init__(overlay)
        self.setWindowTitle("Subtitle Settings")
        self.overlay = overlay
        layout = QVBoxLayout(self)
        
        # Font size
        font_label = QLabel("Font Size")
        font_slider = QSlider(Qt.Horizontal)
        font_slider.setRange(16, 64)
        font_slider.setValue(overlay.font_size)
        font_slider.valueChanged.connect(overlay.set_font_size)
        layout.addWidget(font_label)
        layout.addWidget(font_slider)
        
        # Text opacity
        text_label = QLabel("Text Opacity")
        text_slider = QSlider(Qt.Horizontal)
        text_slider.setRange(10, 100)
        text_slider.setValue(int(overlay.text_opacity * 100))
        text_slider.valueChanged.connect(lambda v: overlay.set_text_opacity(v/100))
        layout.addWidget(text_label)
        layout.addWidget(text_slider)
        
        # Toggle
        toggle = QCheckBox("Show Subtitles")
        toggle.setChecked(overlay._visible)
        toggle.stateChanged.connect(lambda state: overlay.set_subtitle_visible(state == 2))
        layout.addWidget(toggle)
        
        # Close
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)


class VideoPlayerScreen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Holoyomi Video Player")
        self.resize(960, 600)
        
        # Check VLC
        try:
            import vlc
        except ImportError:
            raise RuntimeError("python-vlc is required. Please install it: pip install python-vlc")
        
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()
        
        # Setup UI
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        vbox = QVBoxLayout(central_widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        
        from PyQt5.QtWidgets import QFrame
        self.video_frame = QFrame(self)
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vbox.addWidget(self.video_frame, stretch=1)
        
        self.subtitle_overlay = SubtitleOverlay(self.video_frame)
        self.subtitle_overlay.setVisible(True)
        self.subtitle_overlay.resize_with_video()
        
        # YouTube-style controls
        controls = QWidget(self)
        controls.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #b3e0ff,
                    stop:0.5 #6ec6ff,
                    stop:1 #2196f3);
            }
        """)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 8, 12, 12)
        controls_layout.setSpacing(8)
        
        # Progress bar (top of controls) with time marker
        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(8)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #fff; font-size: 16px; font-family: 'Varela Round', 'Segoe UI', Arial, sans-serif; font-weight: bold; padding-right: 8px; text-shadow: 1px 1px 2px #2196f3;")
        progress_row.addWidget(self.time_label)

        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.position_slider.setFixedHeight(24)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #e3f2fd;
                border-radius: 4px;
                margin: 12px 0;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2196f3, stop:1 #ffe600);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #fff;
                border: 3px solid #2196f3;
                width: 22px;
                height: 22px;
                margin: -9px 0;
                border-radius: 11px;
                box-shadow: 0 0 10px #2196f3;
            }
            QSlider::handle:horizontal:hover {
                background: #ffe600;
                border: 3px solid #fff;
                width: 24px;
                height: 24px;
                margin: -10px 0;
                border-radius: 12px;
                box-shadow: 0 0 14px #ffe600;
            }
        """)
        progress_row.addWidget(self.position_slider, stretch=1)
        controls_layout.addLayout(progress_row)
        
        # Button row
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.setContentsMargins(4, 0, 4, 0)
        
        # Play/Pause button
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.setToolTip("Play (k)")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 20px;
                color: white;
                padding: 8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.25);
            }
        """)
        self.play_btn.clicked.connect(self.toggle_play)
        button_row.addWidget(self.play_btn)
        
        # Volume button + slider
        self.volume_btn = QPushButton("🔊")
        self.volume_btn.setFixedSize(40, 40)
        self.volume_btn.setCursor(Qt.PointingHandCursor)
        self.volume_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 20px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        button_row.addWidget(self.volume_btn)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setToolTip("Volume")
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setFixedHeight(20)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3px;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 1.5px;
                margin: 8px 0;
            }
            QSlider::sub-page:horizontal {
                background: white;
                border-radius: 1.5px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                width: 14px;
                height: 14px;
                margin: -6px 0;
                border-radius: 7px;
            }
        """)
        self.volume_slider.valueChanged.connect(self.set_volume)
        button_row.addWidget(self.volume_slider)
        
        # Spacer
        button_row.addStretch()
        
        # Subtitle settings button
        self.subtitle_settings_btn = QPushButton()
        self.subtitle_settings_btn.setText("CC")
        self.subtitle_settings_btn.setToolTip("Subtitle Settings")
        self.subtitle_settings_btn.setFixedSize(40, 40)
        self.subtitle_settings_btn.setCursor(Qt.PointingHandCursor)
        self.subtitle_settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 20px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.25);
            }
        """)
        self.subtitle_settings_btn.clicked.connect(self.subtitle_overlay.show_settings)
        button_row.addWidget(self.subtitle_settings_btn)
        
        # Settings button (gear icon)
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setFixedSize(40, 40)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 20px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        button_row.addWidget(self.settings_btn)
        
        # Fullscreen button
        self.fullscreen_btn = QPushButton()
        self.fullscreen_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.fullscreen_btn.setToolTip("Fullscreen (f)")
        self.fullscreen_btn.setFixedSize(40, 40)
        self.fullscreen_btn.setCursor(Qt.PointingHandCursor)
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 20px;
                color: white;
                padding: 8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.25);
            }
        """)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        button_row.addWidget(self.fullscreen_btn)
        
        controls_layout.addLayout(button_row)
        
        controls.setFixedHeight(80)
        self.controls = controls
        vbox.addWidget(self.controls)
        
        # Event filters
        self.video_frame.installEventFilter(self)
        
        # Pipeline setup
        self.pipeline_thread = None
        self.translation_cache = {}
        self.processing_done = threading.Event()
        self.translator = JPToENTranslator() if USE_TRANSLATION else None
        
        # Signals for thread-safe updates
        self.signals = SubtitleSignals()
        self.signals.update_text.connect(self._update_subtitle_slot)
        
        # UI update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.ui_update_loop)
        self.update_timer.start(100)

    def eventFilter(self, obj, event):
        if obj == self.video_frame and event.type() == event.Resize:
            self.subtitle_overlay.resize_with_video()
            self.controls.move(0, self.video_frame.height() - self.controls.height())
            self.controls.setFixedWidth(self.video_frame.width())
        return super().eventFilter(obj, event)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def load_video(self, path):
        # Set up VLC video output
        self.video_frame.show()
        self.video_frame.repaint()
        self.video_frame.raise_()
        app = QApplication.instance()
        app.processEvents()
        if sys.platform.startswith('linux'):
            self.vlc_player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.vlc_player.set_hwnd(int(self.video_frame.winId()))
        elif sys.platform == "darwin":
            self.vlc_player.set_nsobject(int(self.video_frame.winId()))
        
        media = self.vlc_instance.media_new(path)
        self.vlc_player.set_media(media)
        self.vlc_player.play()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        
        # Extract audio from video to temp WAV
        audio_path = os.path.splitext(path)[0] + "_holoyomi_temp.wav"
        if not os.path.exists(audio_path):
            try:
                print(f"[INFO] Extracting audio to {audio_path}...")
                (
                    ffmpeg
                    .input(path)
                    .output(audio_path, acodec='pcm_s16le', ac=1, ar=SAMPLERATE, loglevel='error')
                    .overwrite_output()
                    .run()
                )
                print("[INFO] Audio extraction complete")
            except Exception as e:
                print(f"[ERROR] Could not extract audio: {e}")
                audio_path = path
        
        # Start pipeline in thread
        self.pipeline_thread = threading.Thread(target=self.run_pipeline, args=(audio_path,), daemon=True)
        self.pipeline_thread.start()

    def toggle_play(self):
        if self.vlc_player.is_playing():
            self.vlc_player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            self.vlc_player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def stop_video(self):
        self.vlc_player.stop()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def set_position(self, position):
        self.vlc_player.set_position(position / 1000.0)

    def set_volume(self, volume):
        self.vlc_player.audio_set_volume(volume)

    def ui_update_loop(self):
        # Update position slider and time marker
        length = self.vlc_player.get_length()
        if length > 0:
            pos = int(self.vlc_player.get_position() * 1000)
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(pos)
            self.position_slider.blockSignals(False)
            cur_sec = int(self.vlc_player.get_time() / 1000)
            total_sec = int(length / 1000)
            def fmt(secs):
                m, s = divmod(secs, 60)
                return f"{m:02}:{s:02}"
            self.time_label.setText(f"{fmt(cur_sec)} / {fmt(total_sec)}")
        else:
            self.time_label.setText("00:00 / 00:00")

    def update_subtitle(self, jp_text, en_text=None):
        """Thread-safe subtitle update - use signals"""
        self.signals.update_text.emit(jp_text, en_text if en_text else "")

    def _update_subtitle_slot(self, jp_text, en_text):
        """Actually update the subtitle (runs in main thread)"""
        if en_text:
            display_text = f"{jp_text}\n{en_text}"
        else:
            display_text = jp_text
        self.subtitle_overlay.set_subtitle(display_text)

    def run_pipeline(self, audio_file):
        """Pipeline: Audio -> ASR -> Translation -> Subtitles"""
        try:
            print(f"[INFO] Starting pipeline with {audio_file}")
            audio_capture = AudioFileCapture(audio_file, chunk_duration=CHUNK_DURATION, samplerate=SAMPLERATE)
            asr = JapaneseASR(model_path=ASR_MODEL_PATH)
            print("[INFO] ASR initialized")
            
            last_text = ""
            while True:
                chunk = audio_capture.get_chunk()
                if chunk is None:
                    break
                
                try:
                    jp_text = asr.recognize(chunk).strip()
                    if jp_text and jp_text != last_text:
                        last_text = jp_text
                        print(f"[ASR] {jp_text}")
                        
                        # Show Japanese immediately
                        self.update_subtitle(jp_text)
                        
                        # Translate if enabled
                        if self.translator:
                            def translate_worker(jp):
                                if jp in self.translation_cache:
                                    en_text = self.translation_cache[jp]
                                else:
                                    en_text = self.translator.translate(jp)
                                    self.translation_cache[jp] = en_text
                                print(f"[EN] {en_text}")
                                self.update_subtitle(jp, en_text)
                            
                            threading.Thread(target=translate_worker, args=(jp_text,), daemon=True).start()
                
                except Exception as e:
                    print(f"[ERROR] Pipeline error: {e}")
            
            print("[INFO] Pipeline finished")
            self.processing_done.set()
        
        except Exception as e:
            print(f"[FATAL] Pipeline failed to start: {e}")
            import traceback
            traceback.print_exc()


class PixelMenu(QWidget):
    def __init__(self, start_callback):
        super().__init__()
        self.setFixedSize(988, 556)
        self.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #b3e0ff,
                stop:0.5 #6ec6ff,
                stop:1 #2196f3);
        """)
        self.city_offset = 0
        self.car_x = 0
        self.star_states = [(random.randint(0, 988), random.randint(20, 180), random.choice([True, False])) for _ in range(18)]
        self.star_timer = 0
        
        # Start animation timer AFTER widget is shown
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate)
        QTimer.singleShot(100, lambda: self.anim_timer.start(50))
        
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        
        title_shadow = QLabel("HOLOYOMI")
        title_shadow.setAlignment(Qt.AlignCenter)
        title_shadow.setStyleSheet("color: #2196f3; font-size: 64px; font-family: 'Varela Round', 'Segoe UI', Arial, sans-serif; font-weight: bold; padding-top: 32px; text-shadow: 2px 2px 8px #fff;")

        title_label = QLabel("HOLOYOMI")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #fff; font-size: 64px; font-family: 'Varela Round', 'Segoe UI', Arial, sans-serif; font-weight: bold; margin-top: -64px; text-shadow: 2px 2px 8px #2196f3;")
        
        vbox.addWidget(title_shadow)
        vbox.addWidget(title_label)
        
        subtitle = QLabel("JP→EN Subtitle Overlay for VTuber Streams")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #ffe600; font-size: 22px; font-family: 'Varela Round', 'Segoe UI', Arial, sans-serif; font-weight: bold; padding-bottom: 8px; text-shadow: 1px 1px 4px #2196f3;")
        vbox.addWidget(subtitle)
        
        self.start_btn = QPushButton("START")
        self.start_btn.setStyleSheet("background: #fff; color: #2196f3; font-size: 32px; font-family: 'Varela Round', 'Segoe UI', Arial, sans-serif; font-weight: bold; border: 4px solid #ffe600; border-radius: 18px; padding: 18px 64px; margin: 32px auto 0 auto; box-shadow: 0 4px 16px #6ec6ff;")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        vbox.addWidget(self.start_btn, alignment=Qt.AlignCenter)
        
        self.setLayout(vbox)
        self.start_btn.clicked.connect(start_callback)

    def animate(self):
        try:
            self.city_offset = (self.city_offset + 2) % 40
            self.car_x = (self.car_x + 8) % (988 + 80)
            self.star_timer += 1
            if self.star_timer % 4 == 0:
                self.star_states = [
                    (x, y, not on if random.random() < 0.2 else on)
                    for (x, y, on) in self.star_states
                ]
            self.update()
        except Exception as e:
            print(f"[ERROR] Animation error: {e}")

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0, QColor("#181c3a"))
            grad.setColorAt(0.5, QColor("#2a2a6f"))
            grad.setColorAt(1, QColor("#3a3a7f"))
            painter.fillRect(self.rect(), QBrush(grad))

            # Stars
            for x, y, on in self.star_states:
                if on:
                    painter.setPen(QColor("#fff"))
                    painter.drawPoint(x, y)
                    painter.drawPoint(x+1, y)
                    painter.drawPoint(x, y+1)

            painter.setPen(Qt.NoPen)

            # City buildings
            for x in range(-self.city_offset, 988, 40):
                h = 60 + (x % 120)
                painter.setBrush(QColor("#222244"))
                painter.drawRect(x, 340-h, 36, h)
                for wx in range(x+6, x+36, 12):
                    for wy in range(340-h+10, 340, 18):
                        if random.random() > 0.5:
                            painter.setBrush(QColor("#ffe600"))
                            painter.drawRect(wx, wy, 6, 10)

            # Reflection
            painter.setOpacity(0.4)
            for x in range(-self.city_offset, 988, 40):
                h = 60 + (x % 120)
                painter.setBrush(QColor("#222244"))
                painter.drawRect(x, 340, 36, h)
            painter.setOpacity(1.0)

            # Car
            car_y = 420
            car_w, car_h = 80, 32
            car_x = self.car_x - 80
            painter.setBrush(QColor("#00ffcc"))
            painter.setPen(QColor("#fff"))
            painter.drawRect(car_x, car_y, car_w, car_h)
            painter.setBrush(QColor("#222244"))
            painter.drawRect(car_x+10, car_y+24, 20, 8)
            painter.drawRect(car_x+50, car_y+24, 20, 8)
            painter.setBrush(QColor("#fff"))
            painter.drawRect(car_x+60, car_y+8, 12, 12)
            painter.drawRect(car_x+8, car_y+8, 12, 12)
        except Exception as e:
            print(f"[ERROR] Animation error: {e}")

def main():
    app = QApplication(sys.argv)
    print("[DEBUG] App started")
    
    main_window = QMainWindow()
    main_window.setWindowTitle("Holoyomi")
    main_window.setGeometry(100, 100, 988, 556)
    
    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)
    vbox = QVBoxLayout(central_widget)
    vbox.setContentsMargins(0, 0, 0, 0)
    vbox.setSpacing(0)

    def start_clicked():
        print("[DEBUG] Start button clicked")
        file_dialog = QFileDialog(main_window)
        file_dialog.setNameFilters(["Video files (*.mp4 *.mkv *.avi *.mov *.flv *.webm)", "All files (*.*)"])
        if not file_dialog.exec_():
            print("[DEBUG] File dialog cancelled")
            return
        
        video_path = file_dialog.selectedFiles()[0]
        if not os.path.exists(video_path):
            QMessageBox.critical(main_window, "File Error", "Selected file does not exist.")
            print("[DEBUG] File does not exist")
            return
        
        print(f"[DEBUG] Loading video: {video_path}")
        
        # Remove menu and show video player
        for i in reversed(range(vbox.count())):
            widget = vbox.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        player = VideoPlayerScreen()
        vbox.addWidget(player)
        player.show()
        player.load_video(video_path)

    menu = PixelMenu(start_clicked)
    vbox.addWidget(menu)
    
    print("[DEBUG] Main window shown")
    main_window.show()
    
    # Process events before starting animations
    app.processEvents()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()