import socket
import random
import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


CONF_AUTOMATIC_ADD = "automatic_add"
CONF_CUSTOM_EFFECT = "custom_effect"
CONF_COLORS = "colors"
CONF_SPEED_PCT = "speed_pct"
CONF_TRANSITION = "transition"
ATTR_MODE = "mode"


SUPPORT_BRIGHTNESS = 1
SUPPORT_EFFECT = 4
SUPPORT_COLOR = 16
SUPPORT_FLUX_LED = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_COLOR
SUPPORT_WHITE_VALUE = 128

# This mode enables white value to be controlled by brightness.
# RGB value is ignored when this mode is specified.
MODE_WHITE = "w"


# List of supported effects which aren't already declared in LIGHT
EFFECT_RED_FADE = "red_fade"
EFFECT_GREEN_FADE = "green_fade"
EFFECT_BLUE_FADE = "blue_fade"
EFFECT_YELLOW_FADE = "yellow_fade"
EFFECT_CYAN_FADE = "cyan_fade"
EFFECT_PURPLE_FADE = "purple_fade"
EFFECT_WHITE_FADE = "white_fade"
EFFECT_RED_GREEN_CROSS_FADE = "rg_cross_fade"
EFFECT_RED_BLUE_CROSS_FADE = "rb_cross_fade"
EFFECT_GREEN_BLUE_CROSS_FADE = "gb_cross_fade"
EFFECT_COLORSTROBE = "colorstrobe"
EFFECT_RED_STROBE = "red_strobe"
EFFECT_GREEN_STROBE = "green_strobe"
EFFECT_BLUE_STROBE = "blue_strobe"
EFFECT_YELLOW_STROBE = "yellow_strobe"
EFFECT_CYAN_STROBE = "cyan_strobe"
EFFECT_PURPLE_STROBE = "purple_strobe"
EFFECT_WHITE_STROBE = "white_strobe"
EFFECT_COLORJUMP = "colorjump"
EFFECT_CUSTOM = "custom"
EFFECT_RANDOM = "random"
EFFECT_COLORLOOP = "colorloop"

CONF_CUSTOM_EFFECT = "custom_effect"
CONF_PROTOCOL = "protocol"

ATTR_MODE = "mode"
ATTR_HS_COLOR = "hs_color"
ATTR_RGB = "rgb"
ATTR_BRIGHTNESS = "brightness"
ATTR_EFFECT = "effect"
ATTR_WHITE_VALUE = "white_value"

MODE_RGB = "rgb"
MODE_RGBW = "rgbw"

EFFECT_CUSTOM_CODE = 0x60

EFFECT_MAP = {
    EFFECT_COLORLOOP: 0x25,
    EFFECT_RED_FADE: 0x26,
    EFFECT_GREEN_FADE: 0x27,
    EFFECT_BLUE_FADE: 0x28,
    EFFECT_YELLOW_FADE: 0x29,
    EFFECT_CYAN_FADE: 0x2A,
    EFFECT_PURPLE_FADE: 0x2B,
    EFFECT_WHITE_FADE: 0x2C,
    EFFECT_RED_GREEN_CROSS_FADE: 0x2D,
    EFFECT_RED_BLUE_CROSS_FADE: 0x2E,
    EFFECT_GREEN_BLUE_CROSS_FADE: 0x2F,
    EFFECT_COLORSTROBE: 0x30,
    EFFECT_RED_STROBE: 0x31,
    EFFECT_GREEN_STROBE: 0x32,
    EFFECT_BLUE_STROBE: 0x33,
    EFFECT_YELLOW_STROBE: 0x34,
    EFFECT_CYAN_STROBE: 0x35,
    EFFECT_PURPLE_STROBE: 0x36,
    EFFECT_WHITE_STROBE: 0x37,
    EFFECT_COLORJUMP: 0x38,
}


FLUX_EFFECT_LIST = sorted(list(EFFECT_MAP)) + [EFFECT_RANDOM]


def setup_platform():
    """Set up the Flux lights."""

    import flux_led

    lights = []
    light_ips = []

    # Find the bulbs on the LAN
    scanner = flux_led.BulbScanner()
    scanner.scan(timeout=10)
    for device in scanner.getBulbInfo():
        ipaddr = device["ipaddr"]
        if ipaddr in light_ips:
            continue
        device["name"] = "{} {}".format(device["id"], ipaddr)
        device[ATTR_MODE] = None
        device[CONF_PROTOCOL] = None
        device[CONF_CUSTOM_EFFECT] = None
        dlight = FluxLight(device)
        lights.append(dlight)
        return dlight


class FluxLight:
    def __init__(self, device):
        """Initialize the light."""
        self._name = device["name"]
        self._ipaddr = device["ipaddr"]
        self._protocol = device[CONF_PROTOCOL]
        self._mode = device[ATTR_MODE]
        self._custom_effect = device[CONF_CUSTOM_EFFECT]
        self._bulb = None
        self._error_reported = False

    def _connect(self):
        """Connect to Flux light."""
        import flux_led

        self._bulb = flux_led.WifiLedBulb(self._ipaddr, timeout=5)
        if self._protocol:
            self._bulb.setProtocol(self._protocol)

        # After bulb object is created the status is updated. We can
        # now set the correct mode if it was not explicitly defined.
        if not self._mode:
            if self._bulb.rgbwcapable:
                self._mode = MODE_RGBW
            else:
                self._mode = MODE_RGB

    def _disconnect(self):
        """Disconnect from Flux light."""
        self._bulb = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._bulb is not None

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._bulb.isOn()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self._mode == MODE_WHITE:
            return self.white_value

        return self._bulb.brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._mode == MODE_RGBW:
            return SUPPORT_FLUX_LED | SUPPORT_WHITE_VALUE

        if self._mode == MODE_WHITE:
            return SUPPORT_BRIGHTNESS

        return SUPPORT_FLUX_LED

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._bulb.getRgbw()[3]

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        if self._custom_effect:
            return FLUX_EFFECT_LIST + [EFFECT_CUSTOM]

        return FLUX_EFFECT_LIST

    @property
    def effect(self):
        """Return the current effect."""
        current_mode = self._bulb.raw_state[3]

        if current_mode == EFFECT_CUSTOM_CODE:
            return EFFECT_CUSTOM

        for effect, code in EFFECT_MAP.items():
            if current_mode == code:
                return effect

        return None

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        if not self.is_on:
            self._bulb.turnOn()

        rgb = kwargs.get(ATTR_RGB)
        # if hs_color:
        #     rgb = color_util.color_hs_to_RGB(*hs_color)
        # else:
        #     rgb = None

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        white = kwargs.get(ATTR_WHITE_VALUE)

        # Show warning if effect set with rgb, brightness, or white level
        if effect and (brightness or white or rgb):
            _LOGGER.warning(
                "RGB, brightness and white level are ignored when"
                " an effect is specified for a flux bulb"
            )

        # Random color effect
        if effect == EFFECT_RANDOM:
            self._bulb.setRgb(
                random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
            )
            return

        if effect == EFFECT_CUSTOM:
            if self._custom_effect:
                self._bulb.setCustomPattern(
                    self._custom_effect[CONF_COLORS],
                    self._custom_effect[CONF_SPEED_PCT],
                    self._custom_effect[CONF_TRANSITION],
                )
            return

        # Effect selection
        if effect in EFFECT_MAP:
            self._bulb.setPresetPattern(EFFECT_MAP[effect], 50)
            return

        # Preserve current brightness on color/white level change
        if brightness is None:
            brightness = self.brightness

        # Preserve color on brightness/white level change
        if rgb is None:
            rgb = self._bulb.getRgb()

        if white is None and self._mode == MODE_RGBW:
            white = self.white_value

        # handle W only mode (use brightness instead of white value)
        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=brightness)

        # handle RGBW mode
        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=white, brightness=brightness)

        # handle RGB mode
        else:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self._bulb.turnOff()

    def update(self):
        """Synchronize state with bulb."""
        if not self.available:
            try:
                self._connect()
                self._error_reported = False
            except socket.error:
                self._disconnect()
                if not self._error_reported:
                    _LOGGER.warning(
                        "Failed to connect to bulb %s, %s", self._ipaddr, self._name
                    )
                    self._error_reported = True
                return

        self._bulb.update_state(retry=2)


if __name__ == "__main__":
    light = setup_platform()
    light.update()
    # light.turn_on(rgb=(0, 0, 100))  # r b g
    # light.turn_on(brightness=20)
    light.turn_on(effect=EFFECT_COLORLOOP)
    # light.turn_off()
