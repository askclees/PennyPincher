import os
import subprocess
import sys
from pathlib import Path

from .base import ScanRunner

SCANNER_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scanners" / "lan_devices_scan.py"


class LanDevicesScanRunner(ScanRunner):
    """Launches scanners/lan_devices_scan.py (nmcli + ping + `ip neighbor`, Linux-only) as a
    subprocess — same rationale as the other scanners: no reactor-reuse constraint forces this,
    it's just kept as a subprocess for consistency and so a slow scan can't block the FastAPI
    server.

    Not exposed as a directly-selectable "New scan" type in the frontend — it's launched from a
    specific network row in a completed wifi_scan's results table, since it only makes sense
    once you know which SSID to target (and are actually connected to it).
    """

    def launch(self, scan_dir, params):
        ssid = params.get("ssid")
        if not ssid:
            raise ValueError("network_devices_scan requires params.ssid")

        interface = params.get("interface")

        cmd = [
            sys.executable, str(SCANNER_SCRIPT),
            "--scan-dir", str(scan_dir.resolve()),
            "--ssid", ssid,
        ]
        if interface:
            cmd += ["--interface", interface]

        log_file = open(scan_dir / "scan.log", "wb")
        return subprocess.Popen(
            cmd,
            env=os.environ.copy(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
