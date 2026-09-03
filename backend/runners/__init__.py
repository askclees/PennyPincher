"""Scan-type plugin registry. Each entry maps a scan_type name to a ScanRunner instance. Adding a
future scan type means writing a new runner module and adding it here — sites.py/scans.py and
the frontend shell need no changes.
"""

from .bluetooth_scan import BluetoothScanRunner
from .lan_devices_scan import LanDevicesScanRunner
from .router_screenshot import RouterScreenshotRunner
from .wifi_scan import WifiScanRunner

RUNNERS = {
    "router_screenshot": RouterScreenshotRunner(),
    "wifi_scan": WifiScanRunner(),
    "bluetooth_scan": BluetoothScanRunner(),
    "network_devices_scan": LanDevicesScanRunner(),
}
