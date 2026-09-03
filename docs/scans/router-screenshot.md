# Router Screenshot (`router_screenshot`)

Logs into a router's web admin UI and screenshots every settings page it can reach — via Scrapy +
scrapy-playwright (`crawler/`), driving a real headless Chromium.

## Params

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `router_url` | string | yes | — | The router's login page URL, e.g. `https://192.168.1.1/login`. Use the real `https://` URL directly rather than an `http://` cert-warning interstitial some routers show first — Chromium is launched with `--ignore-certificate-errors`, so self-signed certs aren't a problem. |
| `password` | string | yes | — | The router's admin password. |
| `username` | string | no | `""` | Leave blank for password-only routers — `FormAuthStrategy` only fills a username field if both one is found on the page *and* you gave it a value. |
| `auth_type` | string | no | `"form"` | `"form"` (HTML login form) or `"basic"` (HTTP Basic Auth). See [Auth types](#auth-types) below. |
| `max_pages` | int | no | `200` | Safety cap on total pages visited (via links *and* nav-button exploration combined) — bounds runaway crawls from link cycles or huge nav menus. |
| `click_nav` | bool | no | `true` | Also explore onClick-driven nav/sidebar buttons, not just real `<a href>` links. See [Nav-button exploration](#nav-button-exploration-click_nav) below. |
| `username_selector` | string | no | auto-detected | CSS selector for the username field, for `auth_type: "form"` logins where auto-detection picks the wrong field. |
| `password_selector` | string | no | auto-detected | CSS selector for the password field. Needed if a login page has more than one real password input, or if auto-detection's honeypot-avoidance heuristic (see below) still guesses wrong. |
| `submit_selector` | string | no | auto-detected | CSS selector for the login form's submit button. |

## Auth types

### `form` — HTML form login

`crawler/pennypincher_crawler/auth/form_auth.py`. Default behavior, no selectors needed, for most
routers:

1. **Password field**: waits for `input[type=password]` to appear, then picks *the* password
   field to fill using a `tabindex` heuristic — some login pages include a hidden decoy password
   input as an anti-bot honeypot (off-screen, `tabindex="-1"` so a real user's keyboard navigation
   never reaches it); the auto-detector skips any password field with `tabindex="-1"` in favor of
   one still in the normal tab order. Override with `password_selector` if a page has more than
   one *real* password field (rare) and this still guesses wrong.
2. **Username field**: if `username` was given, finds the input immediately preceding the chosen
   password field in DOM order (within the same `<form>`, or the whole document if there isn't
   one). A router with no username field at all simply has no candidate here and this step is
   skipped — nothing gets typed into anything unintended.
3. **Submit**: clicks the form's submit control (`button[type=submit]`, `input[type=submit]`, or
   a bare `<button>` with no `type` attribute at all). Some login pages start this button
   `disabled` until the password field has content (a normal React/Vue pattern) — the click waits
   up to ~2 seconds for it to become enabled rather than assuming it already is.

### `basic` — HTTP Basic Auth

`crawler/pennypincher_crawler/auth/basic_auth.py`. Credentials are supplied at the Playwright
browser-context level (`http_credentials`) before the first navigation — there's no form to fill,
Playwright answers the browser's native auth challenge directly. `username`/`password` are used
as given; `username_selector`/`password_selector`/`submit_selector` don't apply.

## Safety model

The crawler is built to be structurally incapable of triggering a destructive action (Reboot,
Factory Reset, Apply, firmware upload, etc.) on the router:

- **Never submits a form** other than the login form. Settings pages get visited and screenshotted
  — never interacted with beyond that.
- **Link-only navigation** by default (`crawler/pennypincher_crawler/link_filter.py`): after
  login, the only source of new pages is `<a href>` targets found in each page's rendered HTML,
  restricted to the router's own origin (host/port) — it won't wander off to an external "support"
  link, for example.
- **`max_pages`** bounds total pages visited regardless of source.

### Nav-button exploration (`click_nav`)

On by default, because many admin UIs (React/Vue SPAs especially) put their real settings
navigation behind onClick-driven buttons instead of links — on one real router tested during
development, real links alone reached only 3 of 22 actual settings pages, the rest sitting behind
sidebar accordion buttons. `crawler/pennypincher_crawler/click_filter.py` implements this with
**two independent safety layers**, not one:

1. **Filter before ever clicking.** A candidate button must be inside a nav/sidebar landmark
   (`<nav>`, `[role=navigation]`, `<aside>`, a class/data-attribute containing "sidebar", or
   shadcn/ui's `data-sidebar="menu-button"` / `data-slot="sidebar-menu-button"` markers — covers
   both semantic-HTML and component-library conventions). It must not be a `type=submit` control,
   must not be inside a `<form>` at all, and its visible text must not match a broad
   danger-keyword list (case-insensitive substring match):

   ```
   reboot, restart, reset, factory, delete, erase, remove, restore, upload, firmware, format,
   wipe, disable, apply, save, confirm, submit, shutdown, power off, poweroff,
   sign out, log out, logout
   ```

2. **Hard backstop while clicking.** Every non-GET network request is blocked (via Playwright
   route interception) for the entire duration of nav-button exploration on a page. So even if a
   button's label doesn't give away that it's destructive, clicking it still can't reach the
   router as a mutating request. This was verified during development with a decoy button whose
   label passed the filter but whose click handler fired a real POST — the POST was aborted and
   the target endpoint never saw it.

Exploration re-scans the page after every click (rather than working off one static list), so
buttons revealed by expanding an accordion-style submenu get picked up too — and any *real*
`<a href>` links revealed that way are queued for the normal link-crawl regardless of whether the
button itself navigated anywhere.

**Known limitation**, shared with the link-only crawl too: a *GET*-based destructive endpoint (bad
API design, but such devices exist) isn't caught by the non-GET block, since GET requests are
allowed through. Pass `click_nav: false` to restrict a scan to real links only if you'd rather not
have any button ever clicked.

### Why the crawl happens on one continuous browser tab

Some admin UIs keep their auth state in `sessionStorage` rather than cookies. `sessionStorage` is
scoped per browsing-context tab — not shared across separate Playwright `Page` objects even within
the same browser context — so following a link via a brand-new `Page` (the naive way to do a
Scrapy `Request`-per-link crawl) would silently lose the session and bounce back to the login
screen. The whole crawl instead happens via `page.goto()` calls on one continuous tab, exactly
like a real user clicking around, which works for both session models (cookie-based sessions
aren't affected either way).

## Output

Each visited page produces, in the scan's `artifacts/` directory:

- `page_NNNN.png` — full-page screenshot.
- `page_NNNN.html` — the page's rendered HTML at capture time (useful for troubleshooting
  selector/detection issues, or as a stored record of exactly what was seen).

`manifest.json` is a list of `{url, screenshot_file, title}` per page, in visit order.

## Requirements

- `playwright install chromium` once, after `pip install -r requirements.txt`.
- No root/sudo needed. No extra OS packages beyond a working Chromium (Playwright manages its own
  browser binary).

## Troubleshooting

- **Login never succeeds / stays on the login page**: check `password_selector` if the page has
  more than one password-type input; check the actual page HTML saved as `artifacts/page_0001.html`
  from a failed attempt.
- **Router reports "a user is logged in"**: some routers' web UIs only allow one active admin
  session at a time and don't expose a way for this tool to release it — close any other browser
  tab/device signed into the router, or wait for its session timeout, then retry.
- **Only a handful of pages found**: try `click_nav: true` if you had it off — most real routers
  need it for full coverage (see above).
