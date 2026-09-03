# Site reports

A standalone summary of everything found at a site — for sharing, filing, or just reading outside
the app — in HTML or Markdown. On a site's page, once at least one scan there has completed:
"Download HTML report" / "Download Markdown report". Implementation: `backend/report.py`.

## What's in it

- **Router Screenshots** — from the single most recent *completed* `router_screenshot` scan at
  the site (there's no cross-scan "master list" concept for these — see below for why).
- **WiFi Networks**, **Bluetooth Devices**, **Network Devices** — each section is that scan
  type's full master list (see [API reference](api-reference.md#get-sitessite_idaggregatescan_type)):
  every network/device ever seen across *all* completed scans of that type at the site, not just
  the latest one, with First Seen / Last Seen / Times Seen columns.

Why router screenshots don't get the master-list treatment: a WiFi network or Bluetooth device has
a natural stable identity to dedup on (BSSID, address, MAC) that's meaningful across separate
scans. A router settings page's "identity" is its URL, which only means something in the context
of the one crawl that discovered it — there's no useful sense in which "merge every
router_screenshot scan's pages together" would represent anything coherent, so the report just
uses the latest crawl's results as-is.

## HTML vs Markdown

| | HTML | Markdown |
|---|---|---|
| Screenshots | Embedded as base64 `data:` URIs — one self-contained file, opens anywhere, no separate assets to keep track of | Not embedded — Markdown doesn't render those portably across viewers/tools. The screenshots table still lists every page's title + URL; get the actual images from the HTML report or that scan's own "Export as .zip" |
| Styling | Matches the app's dark theme | Plain tables — pastes cleanly into docs/tickets/wikis |
| Typical size | Can be several MB for a large `router_screenshot` scan (proportional to how many pages × screenshot size) | A few KB — just text |

Both are generated fresh on each request (not cached/stored) and downloaded with a
`Content-Disposition: attachment` filename of `{site_id}-report.html` / `{site_id}-report.md`.

## Untrusted content is escaped

Site notes, scan titles, and anything else that ends up in the HTML report is HTML-escaped before
being written in — none of it is trusted as raw markup, so nothing in there (however it got
there) can break out of its table cell/caption. Verified directly in
`tests/test_report.py::test_html_escapes_untrusted_looking_content`.

## Testing

`tests/test_report.py` covers both generators against a temporary data directory (an empty site,
a site with a real screenshot artifact — asserting its exact base64 encoding appears in the HTML
output — a site with cross-scan-deduplicated master-list data, and the HTML-escaping /
Markdown-pipe-escaping checks above). No live router or GUI needed. The reports shown in this doc's
description were additionally verified against a real router scan during development — a genuine
~1.8MB, 22-screenshot HTML report that rendered correctly in a real browser.
