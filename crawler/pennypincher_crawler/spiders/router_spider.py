import json
import os
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

import scrapy

from ..auth import STRATEGIES
from ..click_filter import TAG_NAV_CANDIDATES_JS, DANGER_KEYWORDS
from ..items import PageScreenshotItem
from ..link_filter import normalize_url, same_origin_links


class RouterSpider(scrapy.Spider):
    """Logs into a router admin UI, then does a link-only BFS crawl of same-origin pages,
    screenshotting each one.

    Safety: the primary source of navigation after login is `<a href>` targets found in each
    page's rendered HTML. This spider never submits a form other than the login form (see
    auth/), so it cannot trigger a Reboot/Factory-Reset/Apply action via a settings form.

    It also explores onClick-driven nav/sidebar buttons by default (options.click_nav = true
    unless explicitly disabled) — common in React/Vue admin UIs that don't use real links for
    navigation, and often the only way to reach most of a router's settings pages (verified: one
    real router only exposed 3 of 22 reachable pages via real links alone). Only buttons that
    pass a conservative filter are ever clicked (click_filter.py: not a form-submit control, not
    inside a <form>, label doesn't match a danger-keyword list) AND every non-GET network request
    is blocked for the duration of the click, so even a wrong filter guess can't reach the router
    as a mutation.

    The whole crawl happens on a single Playwright Page/browser tab rather than one Scrapy
    Request (and therefore one fresh Playwright Page) per link. Some admin UIs keep their auth
    state in sessionStorage rather than cookies — sessionStorage is scoped per browsing-context
    tab, not shared across separate Page objects even within the same browser context — so
    navigating a followed link via a brand-new Page would silently lose the session and bounce
    back to the login screen. Following links via `page.goto()` on the same tab (exactly like a
    real user clicking around) works for both session models.
    """

    name = "router_spider"

    def __init__(self, scan_dir=None, router_url=None, auth_type="form", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not scan_dir or not router_url:
            raise ValueError("scan_dir and router_url are required spider arguments (-a)")

        self.scan_dir = Path(scan_dir)
        self.router_url = router_url

        strategy_cls = STRATEGIES.get(auth_type)
        if strategy_cls is None:
            raise ValueError(f"Unknown auth_type: {auth_type!r} (known: {sorted(STRATEGIES)})")

        options = json.loads(os.environ.get("PENNYPINCHER_OPTIONS", "{}"))
        self.max_pages = int(options.pop("max_pages", 200))
        self.click_nav = bool(options.pop("click_nav", True))
        self.auth = strategy_cls(
            username=os.environ["PENNYPINCHER_USERNAME"],
            password=os.environ["PENNYPINCHER_PASSWORD"],
            **options,
        )

        self.allowed_origin = urlsplit(router_url).netloc
        self.visited = set()
        self._clicked_labels = set()

    async def start(self):
        yield scrapy.Request(
            self.router_url,
            callback=self.parse_page,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_context_kwargs": self.auth.context_options(),
            },
            errback=self.on_error,
        )

    async def parse_page(self, response):
        """Bootstraps Playwright via a single Scrapy Request, then drives the entire crawl
        in-page (see class docstring) using a same-origin-link work queue."""
        page = response.meta["playwright_page"]
        pending = deque()

        try:
            await self.auth.login(page, self.router_url)

            async for item in self._visit_and_capture(page, pending):
                yield item

            while pending and len(self.visited) < self.max_pages:
                next_url = pending.popleft()
                if normalize_url(next_url) in self.visited:
                    continue
                try:
                    await page.goto(next_url, wait_until="networkidle", timeout=30000)
                except Exception as exc:
                    self.logger.warning("Navigation to %s failed: %s", next_url, exc)
                    continue
                async for item in self._visit_and_capture(page, pending):
                    yield item
        finally:
            await page.close()

    async def _visit_and_capture(self, page, pending):
        """Captures the page currently loaded in `page`, queues its same-origin links into
        `pending`, and (if enabled) explores its nav/sidebar buttons too. Yields
        PageScreenshotItems for everything captured."""
        if len(self.visited) >= self.max_pages:
            return

        current_url = normalize_url(page.url)
        if current_url in self.visited:
            return
        self.visited.add(current_url)

        captures = [await self._capture(page)]
        if self.click_nav:
            async for captured in self._explore_nav_clicks(page, pending):
                captures.append(captured)

        for url, screenshot_file, title, html in captures:
            yield PageScreenshotItem(url=url, screenshot_file=screenshot_file, title=title)
            for absolute in same_origin_links(html, url, self.allowed_origin):
                if normalize_url(absolute) not in self.visited:
                    pending.append(absolute)

    async def _capture(self, page):
        """Screenshots the current page (and saves its rendered HTML alongside it, for the
        record and for troubleshooting auto-detection issues) and returns (url, screenshot_file,
        title, html). Caller is responsible for having already added the normalized URL to
        self.visited."""
        title = await page.title()
        page_number = f"{len(self.visited):04d}"
        screenshot_name = f"page_{page_number}.png"
        await page.screenshot(
            path=str(self.scan_dir / "artifacts" / screenshot_name), full_page=True
        )
        html = await page.content()
        (self.scan_dir / "artifacts" / f"page_{page_number}.html").write_text(html)
        return page.url, screenshot_name, title, html

    async def _explore_nav_clicks(self, page, pending):
        """Repeatedly tags and clicks conservative-filtered nav/sidebar buttons on the current
        page, yielding a capture for each one that actually changes the URL. Re-scans after every
        click (rather than working off one static list) so buttons revealed by expanding an
        accordion-style submenu get picked up too.

        Some of those buttons are accordion/submenu *toggles* — clicking "Advanced Settings"
        might not navigate anywhere itself, just reveal real `<a href>` sub-items in the DOM. So
        every click's resulting page is scanned for same-origin links into `pending` regardless
        of whether the click changed the URL enough to count as a new page in its own right.

        The non-GET network block is armed for the whole exploration phase (registered once,
        awaited, *then* the click loop starts) rather than per click — registering and clicking
        back-to-back left a race where a JS-dispatched click's synchronous fetch() could fire
        before the browser process had fully armed the just-registered route handler.
        """

        async def block_mutating(route):
            if route.request.method.upper() in ("GET", "HEAD", "OPTIONS"):
                await route.continue_()
            else:
                await route.abort()

        await page.route("**/*", block_mutating)
        try:
            while len(self.visited) < self.max_pages:
                candidates = await page.evaluate(TAG_NAV_CANDIDATES_JS, list(DANGER_KEYWORDS))
                unvisited = [c for c in candidates if c["text"] not in self._clicked_labels]
                if not unvisited:
                    return

                candidate = unvisited[0]
                self._clicked_labels.add(candidate["text"])
                selector = f'[data-pp-candidate="{candidate["index"]}"]'

                try:
                    # A JS-dispatched click (like the login submit button already uses) rather
                    # than Playwright's page.click(), which enforces strict actionability checks
                    # (fully unobscured, not animating) that some component libraries —
                    # Radix/shadcn's tooltip-wrapped sidebar buttons among them — routinely fail
                    # or time out on.
                    await page.eval_on_selector(selector, "(el) => el.click()")
                    try:
                        # Best-effort settle: some dashboards poll continuously in the
                        # background, so "networkidle" may never truly happen — a timeout here
                        # isn't fatal.
                        await page.wait_for_load_state("networkidle", timeout=4000)
                    except Exception:
                        await page.wait_for_timeout(500)
                except Exception as exc:
                    self.logger.warning("Nav click on %r failed: %s", candidate["text"], exc)
                    continue

                html_now = await page.content()
                for absolute in same_origin_links(html_now, page.url, self.allowed_origin):
                    if normalize_url(absolute) not in self.visited:
                        pending.append(absolute)

                new_url = normalize_url(page.url)
                if new_url in self.visited:
                    continue
                self.visited.add(new_url)
                yield await self._capture(page)
        finally:
            await page.unroute("**/*", block_mutating)

    async def on_error(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        self.logger.error("Request failed: %s", failure)
