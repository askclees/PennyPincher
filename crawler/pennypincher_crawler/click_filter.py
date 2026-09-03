"""Safety filter for the opt-in nav-button exploration feature (see spiders/router_spider.py).

Some router admin UIs (particularly React/Vue SPAs) implement their main settings navigation
with onClick-driven buttons instead of real `<a href>` links, which the link-only crawler
(link_filter.py) structurally cannot see. This module defines the *candidate* filter used before
ever clicking such a button — but it is deliberately not the only safety net: router_spider.py
also blocks every non-GET network request for the duration of any exploratory click, so a wrong
guess here still can't reach the router as a mutating request.
"""

# Substrings (case-insensitive) that exclude a button from being clicked during nav exploration.
# Deliberately broad/conservative — a false positive here just means a settings page goes
# unexplored, which is a much smaller cost than a false negative.
DANGER_KEYWORDS = (
    "reboot",
    "restart",
    "reset",
    "factory",
    "delete",
    "erase",
    "remove",
    "restore",
    "upload",
    "firmware",
    "format",
    "wipe",
    "disable",
    "apply",
    "save",
    "confirm",
    "submit",
    "shutdown",
    "power off",
    "poweroff",
    "sign out",
    "log out",
    "logout",
)


def is_dangerous_label(text):
    lower = (text or "").strip().lower()
    return any(word in lower for word in DANGER_KEYWORDS)


# Tags every candidate nav button in the current DOM with a `data-pp-candidate` attribute (so
# Python can click it by a plain, reliable CSS selector afterwards — no fragile selector
# generation needed) and returns their {index, text}. A "candidate" is a <button> (or
# role="button" element) that isn't a form-submit control and whose label doesn't match a danger
# keyword — found two ways:
#   1. Known nav-button markers seen in the wild (e.g. shadcn/ui's Sidebar component marks its
#      own menu buttons with data-sidebar="menu-button" — note this attribute sits on the button
#      itself, not a wrapping container, which is why this is matched directly rather than via
#      the landmark-descendant search below).
#   2. Generically: any <button>/[role=button] found inside a semantic nav/sidebar landmark.
# Both are unioned and de-duplicated, then run through the same filters — repeated scans across
# an expanding accordion menu re-tag existing candidates consistently since the attribute persists.
TAG_NAV_CANDIDATES_JS = """
(dangerWords) => {
    const directMarkers = Array.from(document.querySelectorAll(
        '[data-sidebar="menu-button"], [data-slot="sidebar-menu-button"]'
    ));

    const landmarks = Array.from(document.querySelectorAll([
        'nav', '[role="navigation"]', 'aside',
        '[class*="sidebar" i]', '[class*="Sidebar"]',
        '[data-slot="sidebar"], [data-slot="sidebar-content"], [data-slot="sidebar-menu"]',
    ].join(', ')));
    const landmarkButtons = landmarks.flatMap(
        (landmark) => Array.from(landmark.querySelectorAll('button, [role="button"]'))
    );

    const seen = new Set();
    const results = [];
    let n = 0;
    for (const el of [...directMarkers, ...landmarkButtons]) {
        if (seen.has(el)) continue;
        seen.add(el);
        const tag = el.tagName.toLowerCase();
        if (tag !== 'button' && el.getAttribute('role') !== 'button') continue;
        if (el.closest('form')) continue;
        if ((el.getAttribute('type') || '').toLowerCase() === 'submit') continue;
        if (el.disabled) continue;
        const text = (el.textContent || '').trim();
        if (!text) continue;
        const lower = text.toLowerCase();
        if (dangerWords.some((w) => lower.includes(w))) continue;
        el.setAttribute('data-pp-candidate', String(n));
        results.push({index: n, text: text.slice(0, 80)});
        n += 1;
    }
    return results;
}
"""
