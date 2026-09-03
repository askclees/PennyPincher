import json
from datetime import datetime, timezone


class ScreenshotManifestPipeline:
    """Writes each captured page into the scan's manifest.json as it's crawled, so the backend
    can report live progress (page_count) while the scan is still running.
    """

    def open_spider(self, spider):
        self.manifest_path = spider.scan_dir / "manifest.json"
        self.entries = []

    def process_item(self, item, spider):
        self.entries.append(
            {
                "url": item["url"],
                "screenshot_file": item["screenshot_file"],
                "title": item.get("title"),
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.manifest_path.write_text(json.dumps(self.entries, indent=2))
        return item
