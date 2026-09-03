"""Generates a site-level report (HTML or Markdown) summarizing everything found there: the
latest router_screenshot scan's gallery, plus the WiFi/Bluetooth/network-device master lists
(every network/device ever seen across all scans of that type at the site — see
scans.get_aggregate()).

There's no "master list" equivalent for router_screenshot (each page is identified by its URL,
which is inherently tied to one scan's crawl, not something to merge across separate crawls the
way a BSSID/address/MAC is) — that section always reflects the single most recent completed scan.
"""
import base64
import html as html_lib
from datetime import datetime, timezone

from . import scans, sites

# Shared column definitions for the master-list sections — one source of truth for both the HTML
# and Markdown renderers, mirroring frontend/app.js's TABLE_COLUMNS pattern.
WIFI_COLUMNS = [
    ("SSID", lambda r: r.get("ssid") or "(hidden)"),
    ("BSSID", lambda r: r.get("bssid") or ""),
    ("Signal", lambda r: f"{r['signal']}%" if r.get("signal") is not None else ""),
    ("Channel", lambda r: r.get("channel") if r.get("channel") is not None else ""),
    ("Frequency", lambda r: r.get("frequency") or ""),
    ("Security", lambda r: r.get("security") or "Open"),
    ("In Use", lambda r: "✓" if r.get("in_use") else ""),
    ("First Seen", lambda r: r.get("first_seen_at") or ""),
    ("Last Seen", lambda r: r.get("last_seen_at") or ""),
    ("Times Seen", lambda r: r.get("times_seen", "")),
]

BLUETOOTH_COLUMNS = [
    ("Address", lambda r: r.get("address") or ""),
    ("Name", lambda r: r.get("name") or "(unnamed)"),
    ("Vendor", lambda r: r.get("vendor") or ""),
    ("RSSI", lambda r: f"{r['rssi']} dBm" if r.get("rssi") is not None else ""),
    ("Manufacturer ID", lambda r: ", ".join(r.get("manufacturer_ids") or [])),
    ("First Seen", lambda r: r.get("first_seen_at") or ""),
    ("Last Seen", lambda r: r.get("last_seen_at") or ""),
    ("Times Seen", lambda r: r.get("times_seen", "")),
]

NETWORK_DEVICE_COLUMNS = [
    ("IP", lambda r: r.get("ip") or ""),
    ("MAC", lambda r: r.get("mac") or ""),
    ("Vendor", lambda r: r.get("vendor") or ""),
    ("Hostname", lambda r: r.get("hostname") or ""),
    ("First Seen", lambda r: r.get("first_seen_at") or ""),
    ("Last Seen", lambda r: r.get("last_seen_at") or ""),
    ("Times Seen", lambda r: r.get("times_seen", "")),
]


def _gather(site_id):
    site = sites.get_site(site_id)
    if site is None:
        raise ValueError(f"site {site_id!r} not found")

    router_scan = scans.latest_scan(site_id, "router_screenshot")
    router_pages = scans.get_manifest(site_id, router_scan["scan_id"]) if router_scan else []

    return {
        "site": site,
        "router_scan": router_scan,
        "router_pages": router_pages,
        "wifi": scans.get_aggregate(site_id, "wifi_scan"),
        "bluetooth": scans.get_aggregate(site_id, "bluetooth_scan"),
        "devices": scans.get_aggregate(site_id, "network_devices_scan"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---- HTML -------------------------------------------------------------

_REPORT_CSS = """
body { background: #0f1115; color: #e6e8eb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 2rem; }
h1 { margin: 0 0 0.25rem; }
h2 { margin-top: 2.5rem; border-bottom: 1px solid #2a2e37; padding-bottom: 0.4rem; }
.meta { color: #9aa1ac; font-size: 0.9rem; }
.empty { color: #9aa1ac; font-style: italic; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9rem; }
th, td { text-align: left; padding: 0.5rem 0.7rem; border-bottom: 1px solid #2a2e37; }
th { color: #9aa1ac; font-size: 0.78rem; text-transform: uppercase; }
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; margin-top: 1rem; }
.gallery figure { margin: 0; background: #171a21; border: 1px solid #2a2e37; border-radius: 8px; overflow: hidden; }
.gallery img { width: 100%; display: block; border-bottom: 1px solid #2a2e37; cursor: zoom-in; }
.gallery figcaption { padding: 0.6rem 0.75rem; font-size: 0.8rem; }
.gallery figcaption .url { color: #9aa1ac; word-break: break-all; }
"""

# Only appended when there's at least one router screenshot — no point shipping lightbox CSS/JS
# in a report that has no gallery to light up. Vanilla JS, no external dependencies (the report
# is a single portable file, so this can't rely on anything the app itself ships). All images are
# already fully embedded as base64 in the gallery thumbnails, so "opening" one full-size needs no
# extra data, just displaying the same src larger. Mirrors the app's own lightbox (open/close,
# prev/next, arrow keys).
_LIGHTBOX_HTML = """
<style>
#lightbox-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); align-items: center; justify-content: center; padding: 2rem; cursor: zoom-out; z-index: 10; }
#lightbox-content { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; max-width: 100%; max-height: 100%; cursor: default; }
#lightbox-content img { max-width: 100%; max-height: 80vh; border-radius: 4px; display: block; }
#lightbox-caption { color: #e6e8eb; font-size: 0.85rem; text-align: center; }
#lightbox-close { position: absolute; top: 1rem; right: 1.5rem; background: none; border: none; color: #e6e8eb; font-size: 2rem; line-height: 1; cursor: pointer; padding: 0.25rem 0.5rem; }
#lightbox-prev, #lightbox-next { position: absolute; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.08); border: 1px solid #2a2e37; color: #e6e8eb; font-size: 2rem; line-height: 1; width: 3rem; height: 3rem; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; }
#lightbox-prev:hover, #lightbox-next:hover { background: rgba(255,255,255,0.16); }
#lightbox-prev { left: 1rem; }
#lightbox-next { right: 1rem; }
</style>
<div id="lightbox-overlay">
  <button id="lightbox-close">&times;</button>
  <button id="lightbox-prev">&lsaquo;</button>
  <div id="lightbox-content"><img id="lightbox-img" src="" alt=""><div id="lightbox-caption"></div></div>
  <button id="lightbox-next">&rsaquo;</button>
</div>
<script>
(function () {
  var images = Array.prototype.map.call(document.querySelectorAll(".gallery img"), function (img) {
    return { src: img.getAttribute("src"), alt: img.getAttribute("alt") || "" };
  });
  if (!images.length) return;

  var current = 0;
  var overlay = document.getElementById("lightbox-overlay");
  var imgEl = document.getElementById("lightbox-img");
  var caption = document.getElementById("lightbox-caption");

  function show(i) {
    current = (i + images.length) % images.length;
    imgEl.src = images[current].src;
    caption.textContent = (current + 1) + " / " + images.length + (images[current].alt ? " — " + images[current].alt : "");
  }
  function open(i) {
    show(i);
    overlay.style.display = "flex";
    document.addEventListener("keydown", onKeydown);
  }
  function close() {
    overlay.style.display = "none";
    document.removeEventListener("keydown", onKeydown);
  }
  function onKeydown(e) {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight") show(current + 1);
    else if (e.key === "ArrowLeft") show(current - 1);
  }
  function stop(fn) {
    return function (e) { e.stopPropagation(); fn(); };
  }

  document.querySelectorAll(".gallery img").forEach(function (img, i) {
    img.addEventListener("click", function () { open(i); });
  });
  overlay.addEventListener("click", close);
  document.getElementById("lightbox-content").addEventListener("click", function (e) { e.stopPropagation(); });
  document.getElementById("lightbox-close").addEventListener("click", stop(close));
  document.getElementById("lightbox-prev").addEventListener("click", stop(function () { show(current - 1); }));
  document.getElementById("lightbox-next").addEventListener("click", stop(function () { show(current + 1); }));
})();
</script>
"""


def _esc(value):
    return html_lib.escape(str(value)) if value not in (None, "") else ""


def _html_table(rows, columns):
    if not rows:
        return '<p class="empty">None found yet.</p>'
    head = "".join(f"<th>{_esc(label)}</th>" for label, _ in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_esc(fn(row))}</td>" for _, fn in columns) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def generate_html_report(site_id):
    data = _gather(site_id)
    site = data["site"]

    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>PennyPincher Report — {_esc(site['address'])}</title>",
        f"<style>{_REPORT_CSS}</style></head><body>",
        f"<h1>{_esc(site['address'])}</h1>",
        f'<p class="meta">Generated {_esc(data["generated_at"])}'
        + (f" · {_esc(site['notes'])}" if site.get("notes") else "")
        + "</p>",
        "<h2>Router Screenshots</h2>",
    ]

    if data["router_scan"]:
        parts.append(
            f'<p class="meta">From scan on {_esc(data["router_scan"]["started_at"])} '
            f'({len(data["router_pages"])} page(s))</p>'
        )
        parts.append('<div class="gallery">')
        for page in data["router_pages"]:
            img_path = scans.artifact_path(site_id, data["router_scan"]["scan_id"], page["screenshot_file"])
            if img_path.exists():
                encoded = base64.b64encode(img_path.read_bytes()).decode("ascii")
                img_tag = f'<img src="data:image/png;base64,{encoded}" alt="{_esc(page.get("title"))}">'
            else:
                img_tag = '<p class="empty">(screenshot missing)</p>'
            parts.append(
                f"<figure>{img_tag}<figcaption><strong>{_esc(page.get('title') or '(untitled)')}</strong>"
                f'<br><span class="url">{_esc(page["url"])}</span></figcaption></figure>'
            )
        parts.append("</div>")
    else:
        parts.append('<p class="empty">No completed router screenshot scan yet.</p>')

    parts.append(f"<h2>WiFi Networks ({len(data['wifi'])})</h2>")
    parts.append(_html_table(data["wifi"], WIFI_COLUMNS))
    parts.append(f"<h2>Bluetooth Devices ({len(data['bluetooth'])})</h2>")
    parts.append(_html_table(data["bluetooth"], BLUETOOTH_COLUMNS))
    parts.append(f"<h2>Network Devices ({len(data['devices'])})</h2>")
    parts.append(_html_table(data["devices"], NETWORK_DEVICE_COLUMNS))
    if data["router_pages"]:
        parts.append(_LIGHTBOX_HTML)
    parts.append("</body></html>")

    return "\n".join(parts)


# ---- Markdown -----------------------------------------------------------


def _md_table(rows, columns):
    if not rows:
        return "_None found yet._"
    header = "| " + " | ".join(label for label, _ in columns) + " |"
    separator = "|" + "|".join(["---"] * len(columns)) + "|"
    body_lines = [
        "| " + " | ".join(str(fn(row)).replace("|", "\\|") for _, fn in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator] + body_lines)


def generate_markdown_report(site_id):
    data = _gather(site_id)
    site = data["site"]

    lines = [f"# {site['address']}", "", f"Generated {data['generated_at']}"]
    if site.get("notes"):
        lines.append(f"\nNotes: {site['notes']}")
    lines += ["", "## Router Screenshots", ""]

    if data["router_scan"]:
        lines.append(
            f"From scan on {data['router_scan']['started_at']} ({len(data['router_pages'])} page(s)). "
            "Images aren't embedded in this Markdown report — use the HTML report, or the scan's own "
            "\"Export as .zip\", to get the actual screenshots."
        )
        lines.append("")
        lines.append("| # | Title | URL |")
        lines.append("|---|---|---|")
        for i, page in enumerate(data["router_pages"], 1):
            title = (page.get("title") or "(untitled)").replace("|", "\\|")
            lines.append(f"| {i} | {title} | {page['url']} |")
    else:
        lines.append("_No completed router screenshot scan yet._")

    lines += ["", f"## WiFi Networks ({len(data['wifi'])})", "", _md_table(data["wifi"], WIFI_COLUMNS)]
    lines += ["", f"## Bluetooth Devices ({len(data['bluetooth'])})", "", _md_table(data["bluetooth"], BLUETOOTH_COLUMNS)]
    lines += ["", f"## Network Devices ({len(data['devices'])})", "", _md_table(data["devices"], NETWORK_DEVICE_COLUMNS)]

    return "\n".join(lines) + "\n"
