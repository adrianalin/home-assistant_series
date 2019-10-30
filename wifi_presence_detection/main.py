from connect_box import ConnectBox
from connect_box.exceptions import ConnectBoxError, ConnectBoxLoginError
from typing import List, Optional
from collections import namedtuple
from datetime import timedelta, datetime
from functools import partial
from typing import Any
import aiohttp
import asyncio
import json
import logging


CONF_HOST = "host"
CONF_PASSWORD = "password"
CONF_HOSTS = "hosts"
CONF_EXCLUDE = "exclude"
CONF_HOME_INTERVAL = "home_interval"
CONF_OPTIONS = "scan_options"

logging.basicConfig(format='%(asctime)-15s %(message)s')
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

Device = namedtuple("Device", ["mac", "name", "ip", "last_update"])

###############################################################################


class DeviceScanner:
    """Device scanner object."""

    def __init__(self):
        self._loop = asyncio.get_running_loop()

    async def async_add_job(self, func, *args, **kwargs):
        """Run async task."""
        try:
            result = await self._loop.run_in_executor(None, partial(func, *args, **kwargs))
            _LOGGER.debug("Result from running task: %s", result)
        except Exception as e:
            _LOGGER.error(e)
        return result

    def scan_devices(self) -> List[str]:
        """Scan for devices."""
        raise NotImplementedError()

    def async_scan_devices(self) -> Any:
        """Scan for devices.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_add_job(self.scan_devices)

    def get_device_name(self, device: str) -> str:
        """Get the name of a device."""
        raise NotImplementedError()

    def async_get_device_name(self, device: str) -> Any:
        """Get the name of a device.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_add_job(self.get_device_name, device)

    def get_extra_attributes(self, device: str) -> dict:
        """Get the extra attributes of a device."""
        raise NotImplementedError()

    def async_get_extra_attributes(self, device: str) -> Any:
        """Get the extra attributes of a device.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.async_add_job(self.get_extra_attributes, device)

###############################################################################################


async def async_get_scanner(config, session):
    """Return the UPC device scanner."""

    connect_box = ConnectBox(session, config[CONF_PASSWORD], host=config[CONF_HOST])

    # Check login data
    try:
        await connect_box.async_initialize_token()
    except ConnectBoxLoginError:
        _LOGGER.error("ConnectBox login data error!")
        return None
    except ConnectBoxError:
        pass

    return UPCDeviceScanner(connect_box)


class UPCDeviceScanner(DeviceScanner):
    """This class queries a router running UPC ConnectBox firmware."""

    def __init__(self, connect_box: ConnectBox):
        """Initialize the scanner."""
        self.connect_box: ConnectBox = connect_box

    async def async_scan_devices(self) -> List[str]:
        """Scan for new devices and return a list with found device IDs."""
        try:
            await self.connect_box.async_get_devices()
        except ConnectBoxError:
            return []

        return [device.mac for device in self.connect_box.devices]

    async def async_get_device_name(self, device: str) -> Optional[str]:
        """Get the device name (the name of the wireless device not used)."""
        for connected_device in self.connect_box.devices:
            if connected_device.mac != device:
                continue
            return connected_device.hostname

        return None

###########################################################################################


def get_scanner(config):
    """Validate the configuration and return a Nmap scanner."""
    return NmapDeviceScanner(config)


class NmapDeviceScanner(DeviceScanner):
    """This class scans for devices using nmap."""

    exclude = []

    def __init__(self, config):
        """Initialize the scanner."""
        super().__init__()
        self.last_results = []

        self.hosts = config[CONF_HOSTS]
        self.exclude = config[CONF_EXCLUDE]
        minutes = config[CONF_HOME_INTERVAL]
        self._options = config[CONF_OPTIONS]
        self.home_interval = timedelta(minutes=minutes)

        _LOGGER.debug("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        _LOGGER.debug("Nmap last results %s", self.last_results)

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result.name for result in self.last_results if result.mac == device
        ]

        if filter_named:
            return filter_named[0]
        return None

    def get_extra_attributes(self, device):
        """Return the IP of the given device."""
        filter_ip = next(
            (result.ip for result in self.last_results if result.mac == device), None
        )
        return {"ip": filter_ip}

    def _update_info(self):
        """Scan the network for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Scanning...")

        from nmap import PortScanner, PortScannerError

        scanner = PortScanner()

        options = self._options

        if self.home_interval:
            boundary = datetime.now() - self.home_interval
            last_results = [
                device for device in self.last_results if device.last_update > boundary
            ]
            if last_results:
                exclude_hosts = self.exclude + [device.ip for device in last_results]
            else:
                exclude_hosts = self.exclude
        else:
            last_results = []
            exclude_hosts = self.exclude
        if exclude_hosts:
            options += " --exclude {}".format(",".join(exclude_hosts))

        try:
            result = scanner.scan(hosts=" ".join(self.hosts), arguments=options)
        except PortScannerError:
            _LOGGER.error("PortScannerError happened!")
            return False

        now = datetime.now()
        for ipv4, info in result["scan"].items():
            if info["status"]["state"] != "up":
                continue
            name = info["hostnames"][0]["name"] if info["hostnames"] else ipv4
            # Mac address only returned if nmap ran as root
            mac = info["addresses"].get("mac")  # or get_mac_address(ip=ipv4)
            if mac is None:
                _LOGGER.info("No MAC address found for %s", ipv4)
                continue
            last_results.append(Device(mac.upper(), name, ipv4, now))

        self.last_results = last_results

        _LOGGER.debug("nmap scan successful")
        return True

###############################################################################################


async def async_main():
    """ This function should print the devices connected to your router. """

    with open('config.json') as f:
        config = json.load(f)

    async with aiohttp.ClientSession() as session:
        print("\nRunning UPC device scanner")
        upc_scanner = await async_get_scanner(config, session)
        if upc_scanner:
            found_devices = await upc_scanner.async_scan_devices()
            for mac in found_devices:
                print(await upc_scanner.async_get_device_name(mac))
        else:
            print("Failed to instantiate UPCScanner!")

    print("\nRunning nmap device scanner")
    nmap_scanner = get_scanner(config)
    found_devices = await nmap_scanner.async_scan_devices()
    for mac in found_devices:
        print(mac)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())