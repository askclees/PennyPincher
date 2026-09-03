import os
import subprocess
import sys
from pathlib import Path

from .base import ScanRunner

SCANNER_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scanners" / "bluetooth_scan.py"


class BluetoothScanRunner(ScanRunner):
    """Launches scanners/bluetooth_scan.py (bleak-based BLE scan, Linux-only) as a subprocess —
    same rationale as WifiScanRunner: no reactor-reuse constraint forces this, it's just kept as
    a subprocess for consistency and so a slow scan can't block the FastAPI server.
    """

    def launch(self, scan_dir, params):
        duration = int(params.get("duration") or 15)
        adapter = params.get("adapter")

        cmd = [
            sys.executable, str(SCANNER_SCRIPT),
            "--scan-dir", str(scan_dir.resolve()),
            "--duration", str(duration),
        ]
        if adapter:
            cmd += ["--adapter", adapter]

        log_file = open(scan_dir / "scan.log", "wb")
        return subprocess.Popen(
            cmd,
            env=os.environ.copy(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
