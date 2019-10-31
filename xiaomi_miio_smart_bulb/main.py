from miio import PhilipsBulb
import json
import logging
from datetime import timedelta
from functools import partial
from math import ceil
import asyncio
import datetime


SUCCESS = ["ok"]

# The light does not accept cct values < 1
CCT_MIN = 1
CCT_MAX = 100

ATTR_COLOR_TEMP = "color_temp"
ATTR_BRIGHTNESS = "brightness"

ATTR_MODEL = "model"
ATTR_DELAYED_TURN_OFF = "delayed_turn_off"
ATTR_SCENE = "scene"
DELAYED_TURN_OFF_MAX_DEVIATION_SECONDS = 4


logging.basicConfig(format='%(asctime)-15s %(message)s')
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class XiaomiPhilipsBulb:
    """Representation of a Xiaomi Philips Bulb."""

    def __init__(self, name, light, model, unique_id):
        """Initialize the light device."""
        self._name = name
        self._light = light
        self._model = model
        self._unique_id = unique_id

        self._brightness = None

        self._available = False
        self._state = None
        self._color_temp = None
        self._state_attrs = {ATTR_SCENE: None, ATTR_DELAYED_TURN_OFF: None, ATTR_MODEL: self._model}

        self._loop = asyncio.get_running_loop()

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a light command handling error messages."""
        from miio import DeviceException

        try:
            result = await self._loop.run_in_executor(None, partial(func, *args, **kwargs))
            _LOGGER.debug("Response received from light: %s", result)
            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            self._available = False
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_COLOR_TEMP in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP]
            percent_color_temp = self.translate(
                color_temp, self.max_mireds, self.min_mireds, CCT_MIN, CCT_MAX
            )

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            percent_brightness = ceil(100 * brightness / 255.0)

        if ATTR_BRIGHTNESS in kwargs and ATTR_COLOR_TEMP in kwargs:
            _LOGGER.debug(
                "Setting brightness and color temperature: "
                "%s %s%%, %s mireds, %s%% cct",
                brightness,
                percent_brightness,
                color_temp,
                percent_color_temp,
            )

            result = await self._try_command(
                "Setting brightness and color temperature failed: " "%s bri, %s cct",
                self._light.set_brightness_and_color_temperature,
                percent_brightness,
                percent_color_temp,
            )

            if result:
                self._color_temp = color_temp
                self._brightness = brightness

        elif ATTR_COLOR_TEMP in kwargs:
            _LOGGER.debug(
                "Setting color temperature: " "%s mireds, %s%% cct",
                color_temp,
                percent_color_temp,
            )

            result = await self._try_command(
                "Setting color temperature failed: %s cct",
                self._light.set_color_temperature,
                percent_color_temp,
            )

            if result:
                self._color_temp = color_temp

        elif ATTR_BRIGHTNESS in kwargs:
            _LOGGER.debug("Setting brightness: %s %s%%", brightness, percent_brightness)

            result = await self._try_command(
                "Setting brightness failed: %s",
                self._light.set_brightness,
                percent_brightness,
            )

            if result:
                self._brightness = brightness

        else:
            await self._try_command("Turning the light on failed.", self._light.on)

    async def async_turn_off(self):
        """Turn the light off."""
        await self._try_command("Turning the light off failed.", self._light.off)

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        try:
            state = await self._loop.run_in_executor(None, self._light.status)
        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
            return

        _LOGGER.debug("Got new state: %s", state)
        self._available = True
        self._state = state.is_on
        self._brightness = ceil((255 / 100.0) * state.brightness)
        self._color_temp = self.translate(
            state.color_temperature, CCT_MIN, CCT_MAX, self.max_mireds, self.min_mireds
        )

        delayed_turn_off = self.delayed_turn_off_timestamp(
            state.delay_off_countdown,
            datetime.datetime.utcnow(),
            self._state_attrs[ATTR_DELAYED_TURN_OFF],
        )

        self._state_attrs.update(
            {ATTR_SCENE: state.scene, ATTR_DELAYED_TURN_OFF: delayed_turn_off}
        )

    async def async_set_delayed_turn_off(self, time_period: timedelta):
        """Set delayed turn off."""
        await self._try_command(
            "Setting the turn off delay failed.",
            self._light.delay_off,
            time_period.total_seconds(),
        )

    @staticmethod
    def delayed_turn_off_timestamp(
        countdown: int, current: datetime, previous: datetime
    ):
        """Update the turn off timestamp only if necessary."""
        if countdown is not None and countdown > 0:
            new = current.replace(microsecond=0) + timedelta(seconds=countdown)

            if previous is None:
                return new

            lower = timedelta(seconds=-DELAYED_TURN_OFF_MAX_DEVIATION_SECONDS)
            upper = timedelta(seconds=DELAYED_TURN_OFF_MAX_DEVIATION_SECONDS)
            diff = previous - new
            if lower < diff < upper:
                return previous

            return new

        return None

    @staticmethod
    def translate(value, left_min, left_max, right_min, right_max):
        """Map a value from left span to right span."""
        left_span = left_max - left_min
        right_span = right_max - right_min
        value_scaled = float(value - left_min) / float(left_span)
        return int(right_min + (value_scaled * right_span))


async def main():
    with open("config.json") as file:
        config = json.load(file)
    light = PhilipsBulb(config["host"], config["token"])
    device = XiaomiPhilipsBulb(config["name"], light, config["model"], None)

    await asyncio.gather(device.async_update())
    # await asyncio.gather(device.async_turn_off())
    # await asyncio.gather(device.async_turn_on())
    # await asyncio.gather(device.async_turn_on(color_temp=333)) #  175  333
    # await asyncio.gather(device.async_turn_on(brightness=190)) # 1 255
    # await asyncio.gather(device.async_set_delayed_turn_off(timedelta(seconds=10)))


if __name__ == "__main__":
    asyncio.run(main())
