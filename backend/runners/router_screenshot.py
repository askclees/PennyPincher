import json
import os
import subprocess
import sys
from pathlib import Path

from .base import ScanRunner

CRAWLER_DIR = Path(__file__).resolve().parent.parent.parent / "crawler"

# username is intentionally not required here — some routers (and HTTP Basic Auth in general)
# use a password-only login with no username field at all.
REQUIRED_PARAMS = ("router_url", "password")


class RouterScreenshotRunner(ScanRunner):
    """Launches the Scrapy + scrapy-playwright crawler (crawler/) as a subprocess.

    Scrapy runs on the Twisted reactor, which can only start once per OS process — it can't be
    invoked in-process, repeatedly, from this long-lived FastAPI server, so each scan gets its
    own `scrapy crawl` subprocess instead.
    """

    def launch(self, scan_dir, params):
        missing = [p for p in REQUIRED_PARAMS if not params.get(p)]
        if missing:
            raise ValueError(f"router_screenshot scan is missing required params: {missing}")

        auth_type = params.get("auth_type", "form")
        options = {
            k: v for k, v in params.items() if k not in ("router_url", "username", "password", "auth_type")
        }

        # Credentials go in the subprocess's env, not its argv, so they never show up in `ps`.
        env = os.environ.copy()
        env["PENNYPINCHER_USERNAME"] = params.get("username") or ""
        env["PENNYPINCHER_PASSWORD"] = params["password"]
        env["PENNYPINCHER_OPTIONS"] = json.dumps(options)

        log_file = open(scan_dir / "crawler.log", "wb")
        return subprocess.Popen(
            [
                # sys.executable (not a bare "scrapy" resolved off PATH) so this works
                # regardless of how the FastAPI process itself was started/activated.
                sys.executable, "-m", "scrapy",
                "crawl", "router_spider",
                "-a", f"scan_dir={scan_dir.resolve()}",
                "-a", f"router_url={params['router_url']}",
                "-a", f"auth_type={auth_type}",
            ],
            cwd=str(CRAWLER_DIR),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
