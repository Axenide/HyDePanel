import os

from fabric.utils import get_relative_path
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from gi.repository import Gtk

import utils.functions as helpers
from services import audio_service, network_service
from services.brightness import Brightness
from services.mpris import MprisPlayerManager
from shared.circle_image import CircleImage
from shared.pop_over import PopOverWindow
from shared.submenu import QuickSubToggle
from shared.widget_container import ButtonWidget
from utils.widget_settings import BarConfig
from utils.widget_utils import (
    get_audio_icon_name,
    get_brightness_icon_name,
    psutil_fabricator,
)
from widgets.media import PlayerBoxStack
from widgets.quick_settings.sliders.mic import MicrophoneSlider
from widgets.quick_settings.submenu.bluetooth import BluetoothSubMenu, BluetoothToggle
from widgets.quick_settings.submenu.power import PowerProfileSubMenu, PowerProfileToggle
from widgets.quick_settings.submenu.wifi import WifiSubMenu, WifiToggle
from widgets.quick_settings.togglers import HyprIdleQuickSetting, HyprSunsetQuickSetting

from .sliders.audio import AudioSlider
from .sliders.brightness import BrightnessSlider


class QuickSettingsButtonBox(Box):
    """A box to display the quick settings buttons."""

    def __init__(self, **kwargs):
        super().__init__(
            orientation="v",
            spacing=4,
            h_align="start",
            v_align="start",
            v_expand=True,
            **kwargs,
        )
        self.grid = Gtk.Grid(
            visible=True,
            row_spacing=10,
            column_spacing=10,
        )

        self.active_submenu = None

        # Bluetooth
        self.bluetooth_toggle = BluetoothToggle(
            submenu=BluetoothSubMenu(),
        )

        # Wifi
        self.wifi_toggle = WifiToggle(
            submenu=WifiSubMenu(),
        )

        self.power_pfl = PowerProfileToggle(submenu=PowerProfileSubMenu())

        self.grid.attach(
            self.wifi_toggle,
            0,
            0,
            2,
            2,
        )

        self.grid.attach(
            self.bluetooth_toggle,
            2,
            0,
            2,
            2,
        )

        self.grid.attach(
            self.power_pfl,
            0,
            2,
            2,
            2,
        )

        self.grid.attach(
            HyprIdleQuickSetting(),
            2,
            2,
            2,
            2,
        )

        self.grid.attach(
            HyprSunsetQuickSetting(),
            0,
            4,
            2,
            2,
        )

        self.wifi_toggle.connect("reveal-clicked", self.set_active_submenu)
        self.bluetooth_toggle.connect("reveal-clicked", self.set_active_submenu)
        self.power_pfl.connect("reveal-clicked", self.set_active_submenu)

        self.add(self.grid)
        self.add(self.wifi_toggle.submenu)
        self.add(self.bluetooth_toggle.submenu)
        self.add(self.power_pfl.submenu)

    def set_active_submenu(self, btn: QuickSubToggle):
        if btn.submenu != self.active_submenu and self.active_submenu is not None:
            self.active_submenu.do_reveal(False)

        self.active_submenu = btn.submenu
        self.active_submenu.toggle_reveal() if self.active_submenu else None


class QuickSettingsMenu(Box):
    """A menu to display the weather information."""

    def __init__(self, config, **kwargs):
        super().__init__(
            name="quicksettings-menu", orientation="v", all_visible=True, **kwargs
        )

        self.config = config

        user_image = (
            get_relative_path("../../assets/images/no_image.jpg")
            if not os.path.exists(os.path.expandvars("$HOME/.face"))
            else os.path.expandvars("$HOME/.face")
        )

        user_label = Label(
            label="User", v_align="center", h_align="start", style_classes="user"
        )

        uptime_label = Label(
            label=helpers.uptime(),
            style_classes="uptime",
            v_align="center",
            h_align="start",
        )

        self.user_box = Gtk.Grid(
            row_spacing=5,
            column_spacing=10,
            name="user-box-grid",
            visible=True,
        )

        self.user_box.attach(
            CircleImage(
                image_file=user_image,
                size=70,
            ),
            0,
            0,
            2,
            2,
        )

        self.user_box.attach(
            user_label,
            2,
            0,
            1,
            1,
        )

        self.user_box.attach(
            uptime_label,
            2,
            1,
            1,
            1,
        )

        box = CenterBox(
            orientation="v",
            style_classes="quick-settings-box",
            start_children=Box(
                orientation="v",
                spacing=10,
                v_align="center",
                style_classes="section-box",
                children=(self.user_box, QuickSettingsButtonBox()),
            ),
            center_children=Box(
                orientation="v",
                spacing=10,
                style_classes="section-box slider-box",
                children=(BrightnessSlider(), AudioSlider(), MicrophoneSlider()),
            ),
            end_children=(
                Box(
                    orientation="v",
                    spacing=10,
                    style_classes="section-box",
                    children=(
                        PlayerBoxStack(
                            MprisPlayerManager(), config=self.config["media"]
                        ),
                    ),
                ),
            ),
        )

        self.add(box)

        psutil_fabricator.connect(
            "changed",
            lambda _, value: (
                user_label.set_label(
                    f"{helpers.get_distro_icon()} {value.get('user')}"
                ),
                uptime_label.set_label(f" {value.get('uptime')}"),
            ),
        )


class QuickSettingsButtonWidget(ButtonWidget):
    """A button to display the date and time."""

    def __init__(self, widget_config: BarConfig, bar, **kwargs):
        super().__init__(name="quick-settings-button", **kwargs)

        self.config = widget_config["quick_settings"]
        self.panel_icon_size = 16
        self.audio = audio_service

        self.network = network_service

        # Initialize the audio service
        self.brightness_service = Brightness().get_initial()

        self.audio.connect("notify::speaker", self.on_speaker_changed)
        self.brightness_service.connect("screen", self.on_brightness_changed)

        popup = PopOverWindow(
            parent=bar,
            name="popup",
            child=(QuickSettingsMenu(config=self.config),),
            visible=False,
            all_visible=False,
        )

        self.audio_icon = Image(style_classes="panel-icon")

        self.network_icon = Image(
            style_classes="panel-icon",
        )

        self.brightness_icon = Image(
            style_classes="panel-icon",
        )

        self.update_brightness()

        popup.set_pointing_to(self)

        self.children = Box(
            children=(
                self.network_icon,
                self.audio_icon,
                self.brightness_icon,
            )
        )
        self.connect(
            "button-press-event",
            lambda *_: popup.set_visible(not popup.get_visible()),
        )

        def get_network_icon(*_):
            if self.network.primary_device == "wifi":
                wifi = self.network.wifi_device
                if wifi:
                    self.network_icon.set_from_icon_name(
                        wifi.get_icon_name(),
                        self.panel_icon_size,
                    )

            else:
                ethernet = self.network.ethernet_device
                if ethernet:
                    self.network_icon.set_from_icon_name(
                        ethernet.get_icon_name(),
                        self.panel_icon_size,
                    )

        self.network.connect("notify::primary-device", get_network_icon)

    def on_speaker_changed(self, *_):
        # Update the progress bar value based on the speaker volume
        if not self.audio.speaker:
            return

        self.audio.speaker.connect("notify::volume", self.update_volume)
        self.update_volume()

    def update_volume(self, *_):
        if self.audio.speaker:
            volume = round(self.audio.speaker.volume)

            self.audio_icon.set_from_icon_name(
                get_audio_icon_name(volume, self.audio.speaker.muted)["icon"],
                self.panel_icon_size,
            )

    def on_brightness_changed(self, *_):
        self.update_brightness()

    def update_brightness(self, *_):
        normalized_brightness = helpers.convert_to_percent(
            self.brightness_service.screen_brightness,
            self.brightness_service.max_screen,
        )

        self.brightness_icon.set_from_icon_name(
            get_brightness_icon_name(normalized_brightness)["icon"],
            self.panel_icon_size,
        )
