import os
import subprocess
import sys
from pathlib import Path

from .base import ScanRunner

SCANNER_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scanners" / "wifi_scan.py"


class WifiScanRunner(ScanRunner):
    """Launches scanners/wifi_scan.py (nmcli-based, Linux-only for now) as a subprocess.

    No Scrapy/Playwright involved here — it's just repeated `nmcli` calls, so unlike
    RouterScreenshotRunner there's no Twisted-reactor constraint forcing a subprocess. It's kept
    as one anyway for consistency with that runner and so a slow scan can't block the FastAPI
    server's event loop.
    """

    def launch(self, scan_dir, params):
        duration = int(params.get("duration") or 15)
        interface = params.get("interface")

        cmd = [
            sys.executable, str(SCANNER_SCRIPT),
            "--scan-dir", str(scan_dir.resolve()),
            "--duration", str(duration),
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
