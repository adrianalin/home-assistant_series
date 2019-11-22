from PySide2.QtWidgets import QMainWindow
from PySide2.QtCore import QTimer
from PySide2 import QtGui
import volume_slider
import const

from ui_mainwindow import Ui_MainWindow
from MPD import setup_platform


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.MPD = setup_platform()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.timer = QTimer(self)
        self.volume_slider = volume_slider.VolumeWidget()
        self.ui.gridLayout_3.addWidget(self.volume_slider, 0, 6)

        self.update()
        self.ui.playlist_widget.addItems(self.MPD.source_list)

        self.ui.playlist_widget.currentItemChanged.connect(self.select_playlist)
        self.ui.songs_widget.currentItemChanged.connect(self.select_song)
        self.volume_slider.valueChanged.connect(self.volume_changed)
        self.ui.play_pause_btn.pressed.connect(self.play_pause)

        self.ui.previous_btn.pressed.connect(
            lambda: self.MPD.media_previous_track()
        )
        self.ui.next_btn.pressed.connect(
            lambda: self.MPD.media_next_track()
        )
        self.ui.mute_button.pressed.connect(self.toggle_mute)

        self.timer.timeout.connect(self.update)
        self.timer.start(10000)

    def toggle_mute(self):
        self.MPD.mute_volume(not self.MPD.is_volume_muted)
        self.volume_slider.setValue(self.MPD.volume_level * 100)

    def update(self):
        self.MPD.update()
        state = self.MPD.state
        media_title = self.MPD.media_title if self.MPD.media_title else "Now playing."

        self.ui.now_playing_label.setText(media_title)
        self.volume_slider.setValue(self.MPD.volume_level * 100)

    def play_pause(self):
        if self.MPD.state == const.STATE_PLAYING:
            self.MPD.media_pause()
            icon = "resources/play.png"
        elif self.MPD.state == const.STATE_PAUSED:
            self.MPD.media_play()
            icon = "resources/pause.png"
        elif self.MPD.state == const.STATE_OFF:
            self.MPD.turn_on()
            icon = "resources/pause.png"
        self.MPD.update()

        play_icon = QtGui.QIcon()
        play_icon.addPixmap(QtGui.QPixmap(icon), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.ui.play_pause_btn.setIcon(play_icon)

    def volume_changed(self, vol):
        self.MPD.set_volume_level(vol / 100)

    def select_song(self, current, previous):
        if current:
            self.MPD.play_media(const.MEDIA_TYPE_MUSIC, current.text())

    def select_playlist(self, current, previous):
        self.ui.songs_widget.clear()
        songs_in_playlist = []
        if current and current.text():
            songs_in_playlist = self.MPD.list_playlist(current.text())
            self.MPD.play_media(const.MEDIA_TYPE_PLAYLIST, current.text())
        if songs_in_playlist:
            self.ui.songs_widget.addItems(songs_in_playlist)


