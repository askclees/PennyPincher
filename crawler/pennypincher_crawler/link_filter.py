"""The crawler's entire navigation safety boundary lives here: only `<a href>` targets are ever
considered, and only if they resolve to the same origin as the router being crawled. Buttons,
onclick handlers, and off-origin links are structurally invisible to this extraction — the spider
has no other way to discover where to navigate next, so it cannot trigger a Reboot/Factory-Reset/
Apply action or wander off to some other site.
"""

from urllib.parse import urljoin, urlsplit, urlunsplit

import scrapy


def normalize_url(url):
    """Collapses trivial URL variants (trailing slash, fragment) so the same page isn't visited
    twice under two different-looking URLs."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def same_origin_links(html, base_url, allowed_origin):
    """Returns every same-origin http(s) link found via `<a href>` in `html`, resolved against
    `base_url`. `allowed_origin` is a host[:port] string (e.g. `urlsplit(router_url).netloc`)."""
    hrefs = scrapy.Selector(text=html, base_url=base_url).css("a::attr(href)").getall()
    links = []
    for href in hrefs:
        absolute = urljoin(base_url, href)
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or parts.netloc != allowed_origin:
            continue
        links.append(absolute)
    return links
