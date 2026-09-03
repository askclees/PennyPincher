BOT_NAME = "pennypincher_crawler"
SPIDER_MODULES = ["pennypincher_crawler.spiders"]
NEWSPIDER_MODULE = "pennypincher_crawler.spiders"

# This crawls a router's own authenticated admin UI, not a public site — robots.txt doesn't apply.
ROBOTSTXT_OBEY = False

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    # Many router admin UIs are served over LAN-only, self-signed HTTPS certs.
    "args": ["--ignore-certificate-errors"],
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000

ITEM_PIPELINES = {
    "pennypincher_crawler.pipelines.ScreenshotManifestPipeline": 100,
}

# Router admin UIs run on modest embedded hardware — keep this gentle by default.
CONCURRENT_REQUESTS = 2
DOWNLOAD_DELAY = 0.5

LOG_LEVEL = "INFO"
