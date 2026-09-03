from abc import ABC, abstractmethod


class ScanRunner(ABC):
    """A scan type's execution strategy. Backend orchestration (site/scan storage, status
    polling, export) is generic across scan types — a runner only needs to launch a subprocess
    that writes manifest.json and files into scan_dir/artifacts/ as it runs.
    """

    @abstractmethod
    def launch(self, scan_dir, params):
        """Starts the scan as a subprocess for `scan_dir` (a Path, already created with an
        artifacts/ subdirectory) using `params` (the scan-type-specific request body). Returns a
        handle with a `.poll()` method (e.g. a subprocess.Popen) that the backend polls for
        completion — poll() returns an exit code once finished, or None while still running.
        """
        raise NotImplementedError
