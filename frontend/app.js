const app = document.getElementById("app");

const SCAN_TYPES = [
  { value: "router_screenshot", label: "Router Screenshot" },
  { value: "wifi_scan", label: "WiFi Scan" },
  { value: "bluetooth_scan", label: "Bluetooth Scan" },
];

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${method} ${path} failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) node.appendChild(child);
  return node;
}

function statusPill(status) {
  return el("span", { class: `status-pill ${status}`, text: status });
}

// ---- Routing ----------------------------------------------------------

function parseRoute() {
  const hash = location.hash.replace(/^#\/?/, "");
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "site" && parts[1] && parts[2] === "scan" && parts[3]) {
    return { view: "scan", siteId: parts[1], scanId: parts[3] };
  }
  if (parts[0] === "site" && parts[1] && parts[2] === "all" && parts[3]) {
    return { view: "aggregate", siteId: parts[1], scanType: parts[3] };
  }
  if (parts[0] === "site" && parts[1]) {
    return { view: "site", siteId: parts[1] };
  }
  return { view: "sites" };
}

async function render() {
  const route = parseRoute();
  app.innerHTML = "";
  try {
    if (route.view === "sites") await renderSitesView();
    else if (route.view === "site") await renderSiteView(route.siteId);
    else if (route.view === "scan") await renderScanView(route.siteId, route.scanId);
    else if (route.view === "aggregate") await renderAggregateView(route.siteId, route.scanType);
  } catch (err) {
    app.appendChild(el("div", { class: "error-box", text: err.message }));
  }
}

async function renderVersion() {
  try {
    const { version } = await api("GET", "/version");
    document.getElementById("version").textContent = `v${version}`;
  } catch {
    // non-essential — leave the badge blank rather than breaking the page over it
  }
}

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", render);
window.addEventListener("DOMContentLoaded", renderVersion);

// ---- Sites view ---------------------------------------------------------

async function renderSitesView() {
  const sites = await api("GET", "/sites");

  const panel = el("div", { class: "panel" });
  panel.appendChild(el("h2", { text: "New site" }));
  const addressInput = el("input", { placeholder: "123 Main St, Springfield" });
  const notesInput = el("input", { placeholder: "Notes (optional)" });
  const button = el("button", {
    text: "Create / open site",
    onclick: async () => {
      if (!addressInput.value.trim()) return;
      const site = await api("POST", "/sites", { address: addressInput.value.trim(), notes: notesInput.value.trim() || null });
      location.hash = `#/site/${site.site_id}`;
    },
  });
  panel.appendChild(el("label", { text: "Address" }));
  panel.appendChild(addressInput);
  panel.appendChild(el("label", { text: "Notes" }));
  panel.appendChild(notesInput);
  panel.appendChild(button);
  app.appendChild(panel);

  const listPanel = el("div", { class: "panel" });
  listPanel.appendChild(el("h2", { text: "Sites" }));
  if (!sites.length) {
    listPanel.appendChild(el("p", { class: "empty", text: "No sites yet." }));
  } else {
    for (const site of sites) {
      const row = el("div", { class: "list-item" }, [
        el("a", { href: `#/site/${site.site_id}`, text: site.address }),
        el("span", { class: "meta", text: `${site.scan_count} scan(s)` }),
      ]);
      listPanel.appendChild(row);
    }
  }
  app.appendChild(listPanel);
}

// ---- Site view ------------------------------------------------------------

async function renderSiteView(siteId) {
  const [site, scanList] = await Promise.all([
    api("GET", `/sites/${siteId}`),
    api("GET", `/sites/${siteId}/scans`),
  ]);

  app.appendChild(el("p", {}, [el("a", { href: "#/", text: "← All sites" })]));
  app.appendChild(el("h2", { text: site.address }));
  if (site.notes) app.appendChild(el("p", { class: "meta", text: site.notes }));

  const formPanel = el("div", { class: "panel" });
  formPanel.appendChild(el("h2", { text: "New scan" }));
  formPanel.appendChild(buildNewScanForm(siteId));
  app.appendChild(formPanel);

  const listPanel = el("div", { class: "panel" });
  listPanel.appendChild(el("h2", { text: "Scans" }));
  if (!scanList.length) {
    listPanel.appendChild(el("p", { class: "empty", text: "No scans yet." }));
  } else {
    for (const scan of scanList.slice().reverse()) {
      const row = el("div", { class: "list-item" }, [
        el("a", {
          href: `#/site/${siteId}/scan/${scan.scan_id}`,
          text: `${scan.scan_type} — ${scan.started_at}`,
        }),
        statusPill(scan.status),
      ]);
      listPanel.appendChild(row);
    }
  }
  app.appendChild(listPanel);

  // "Master list" — every network/device seen across ALL scans of a type at this site, not just
  // one scan's results. Only offered once there's at least one completed scan of that type.
  const AGGREGATE_TYPES = [
    { type: "wifi_scan", label: "All WiFi networks seen at this site" },
    { type: "bluetooth_scan", label: "All Bluetooth devices seen at this site" },
  ];
  const available = AGGREGATE_TYPES.filter((t) =>
    scanList.some((s) => s.scan_type === t.type && s.status === "done"));
  if (available.length) {
    const aggPanel = el("div", { class: "panel" });
    aggPanel.appendChild(el("h2", { text: "Master lists" }));
    for (const { type, label } of available) {
      aggPanel.appendChild(el("p", {}, [el("a", { href: `#/site/${siteId}/all/${type}`, text: label })]));
    }
    app.appendChild(aggPanel);
  }

  // Site report — a standalone HTML or Markdown summary (router screenshot gallery + the WiFi/
  // Bluetooth/network-device master lists), for sharing or filing outside the app. Only offered
  // once there's something to report on.
  if (scanList.some((s) => s.status === "done")) {
    const reportPanel = el("div", { class: "panel" });
    reportPanel.appendChild(el("h2", { text: "Report" }));
    reportPanel.appendChild(el("p", {
      class: "meta",
      text: "Router screenshots from the latest scan, plus the full WiFi/Bluetooth/network-device master lists.",
    }));
    reportPanel.appendChild(el("button", {
      text: "Download HTML report",
      onclick: () => window.open(`/sites/${siteId}/report/html`, "_blank"),
    }));
    reportPanel.appendChild(el("button", {
      class: "secondary",
      text: "Download Markdown report",
      onclick: () => window.open(`/sites/${siteId}/report/markdown`, "_blank"),
    }));
    app.appendChild(reportPanel);
  }
}

function buildNewScanForm(siteId) {
  const form = el("div");

  const typeSelect = el("select", {}, SCAN_TYPES.map((t) => el("option", { value: t.value, text: t.label })));
  form.appendChild(el("label", { text: "Scan type" }));
  form.appendChild(typeSelect);

  const routerFields = el("div");
  const wifiFields = el("div");
  const bluetoothFields = el("div");
  form.appendChild(routerFields);
  form.appendChild(wifiFields);
  form.appendChild(bluetoothFields);

  const syncFieldVisibility = () => {
    routerFields.style.display = typeSelect.value === "router_screenshot" ? "" : "none";
    wifiFields.style.display = typeSelect.value === "wifi_scan" ? "" : "none";
    bluetoothFields.style.display = typeSelect.value === "bluetooth_scan" ? "" : "none";
  };
  typeSelect.addEventListener("change", syncFieldVisibility);

  const authSelect = el("select", {}, [
    el("option", { value: "form", text: "HTML form login" }),
    el("option", { value: "basic", text: "HTTP Basic Auth" }),
  ]);
  const routerUrl = el("input", { placeholder: "https://192.168.1.1/" });
  const username = el("input", { placeholder: "admin (leave blank if the router only asks for a password)" });
  const password = el("input", { type: "password" });
  const maxPages = el("input", { type: "number", value: "200", min: "1" });
  const usernameSel = el("input", { placeholder: "e.g. #username (optional)" });
  const passwordSel = el("input", { placeholder: "e.g. input[type=password] (optional)" });
  const submitSel = el("input", { placeholder: "e.g. button#login (optional)" });
  const clickNav = el("input", { type: "checkbox", checked: true });

  routerFields.appendChild(el("label", { text: "Router URL" }));
  routerFields.appendChild(routerUrl);
  routerFields.appendChild(el("label", { text: "Auth type" }));
  routerFields.appendChild(authSelect);
  routerFields.appendChild(el("label", { text: "Username" }));
  routerFields.appendChild(username);
  routerFields.appendChild(el("label", { text: "Password" }));
  routerFields.appendChild(password);

  const details = el("details", { class: "advanced" });
  details.appendChild(el("summary", { text: "Advanced (field selectors, max pages)" }));
  const advBody = el("div");
  advBody.appendChild(el("label", { text: "Username field CSS selector" }));
  advBody.appendChild(usernameSel);
  advBody.appendChild(el("label", { text: "Password field CSS selector" }));
  advBody.appendChild(passwordSel);
  advBody.appendChild(el("label", { text: "Submit button CSS selector" }));
  advBody.appendChild(submitSel);
  advBody.appendChild(el("label", { text: "Max pages" }));
  advBody.appendChild(maxPages);
  const clickNavLabel = el("label", {}, [
    clickNav,
    document.createTextNode(
      " Explore nav/sidebar buttons, not just links (on by default — most routers hide settings" +
      " pages behind these) — never clicks anything labeled like a destructive action, and" +
      " blocks all non-GET requests during exploration as a hard backstop. Uncheck to restrict" +
      " the crawl to real links only."
    ),
  ]);
  clickNavLabel.style.display = "flex";
  clickNavLabel.style.gap = "0.4rem";
  clickNavLabel.style.alignItems = "flex-start";
  clickNavLabel.style.marginTop = "0.75rem";
  advBody.appendChild(clickNavLabel);
  details.appendChild(advBody);
  routerFields.appendChild(details);

  const duration = el("input", { type: "number", value: "15", min: "1" });
  const interfaceInput = el("input", { placeholder: "e.g. wlan0 (optional — defaults to nmcli's own choice)" });
  wifiFields.appendChild(el("label", { text: "Scan duration (seconds)" }));
  wifiFields.appendChild(duration);
  wifiFields.appendChild(el("label", { text: "WiFi interface" }));
  wifiFields.appendChild(interfaceInput);
  wifiFields.appendChild(el("p", {
    class: "meta",
    text: "Rescans repeatedly for the given duration, keeping each network's latest reading — " +
      "useful if walking around a site while it runs. Linux only, via nmcli.",
  }));

  const btDuration = el("input", { type: "number", value: "15", min: "1" });
  const btAdapter = el("input", { placeholder: "e.g. hci0 (optional — defaults to bleak's own choice)" });
  bluetoothFields.appendChild(el("label", { text: "Scan duration (seconds)" }));
  bluetoothFields.appendChild(btDuration);
  bluetoothFields.appendChild(el("label", { text: "Bluetooth adapter" }));
  bluetoothFields.appendChild(btAdapter);
  bluetoothFields.appendChild(el("p", {
    class: "meta",
    text: "Scans continuously for the given duration via bleak (BlueZ over D-Bus). Linux only, " +
      "and needs bluetoothd running with a working adapter.",
  }));

  syncFieldVisibility();

  const errorBox = el("div", { class: "error-box", style: "display:none" });
  form.appendChild(errorBox);

  const submitButton = el("button", {
    text: "Start scan",
    onclick: async () => {
      errorBox.style.display = "none";
      submitButton.disabled = true;
      try {
        let params;
        if (typeSelect.value === "wifi_scan") {
          params = { duration: Number(duration.value) || 15 };
          if (interfaceInput.value.trim()) params.interface = interfaceInput.value.trim();
        } else if (typeSelect.value === "bluetooth_scan") {
          params = { duration: Number(btDuration.value) || 15 };
          if (btAdapter.value.trim()) params.adapter = btAdapter.value.trim();
        } else {
          params = {
            router_url: routerUrl.value.trim(),
            auth_type: authSelect.value,
            username: username.value,
            password: password.value,
            max_pages: Number(maxPages.value) || 200,
            // Explicit true/false, not conditionally included — the backend defaults to true
            // when this key is omitted, so an unchecked box must still send click_nav: false.
            click_nav: clickNav.checked,
          };
          if (usernameSel.value.trim()) params.username_selector = usernameSel.value.trim();
          if (passwordSel.value.trim()) params.password_selector = passwordSel.value.trim();
          if (submitSel.value.trim()) params.submit_selector = submitSel.value.trim();
        }

        const scan = await api("POST", `/sites/${siteId}/scans`, { scan_type: typeSelect.value, params });
        location.hash = `#/site/${siteId}/scan/${scan.scan_id}`;
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
      } finally {
        submitButton.disabled = false;
      }
    },
  });
  form.appendChild(submitButton);
  return form;
}

// ---- Scan view --------------------------------------------------------

let pollTimer = null;

async function renderScanView(siteId, scanId) {
  if (pollTimer) clearTimeout(pollTimer);

  const scan = await api("GET", `/sites/${siteId}/scans/${scanId}`);

  const countLabel = COUNT_LABELS[scan.scan_type] || "page(s) captured";
  app.appendChild(el("p", {}, [el("a", { href: `#/site/${siteId}`, text: "← Back to site" })]));
  app.appendChild(el("h2", {}, [document.createTextNode(`${scan.scan_type} `), statusPill(scan.status)]));
  app.appendChild(el("p", { class: "meta", text: `Started ${scan.started_at}${scan.page_count != null ? ` · ${scan.page_count} ${countLabel}` : ""}` }));

  if (scan.status === "error") {
    app.appendChild(el("div", { class: "error-box", text: scan.error || "Scan failed." }));
  }

  if (scan.status === "running" || scan.status === "pending") {
    app.appendChild(el("p", { class: "empty", text: "Scan in progress… this page updates automatically." }));
    pollTimer = setTimeout(render, 2000);
    return;
  }

  const exportLink = el("a", { href: `/sites/${siteId}/scans/${scanId}/export`, text: "Export as .zip" });
  const exportButton = el("button", { class: "secondary", onclick: () => window.open(exportLink.href, "_blank") }, [document.createTextNode("Export as .zip")]);
  app.appendChild(exportButton);

  let results = await api("GET", `/sites/${siteId}/scans/${scanId}/results`);
  if (!results.length) {
    app.appendChild(el("p", { class: "empty", text: EMPTY_LABELS[scan.scan_type] || "No pages captured." }));
    return;
  }

  if (scan.scan_type === "wifi_scan") {
    results = groupWifiNetworksBySsid(results);
  }

  const columns = TABLE_COLUMNS[scan.scan_type];
  if (columns) {
    app.appendChild(renderTable(results, columns, { siteId }));
  } else {
    app.appendChild(renderGallery(siteId, scanId, results));
  }
}

// Dual-band routers and mesh systems commonly broadcast one SSID across several access points
// (different BSSID/channel each) — shown separately that reads as "duplicates" of the same
// network. This groups the results table by SSID for display only; the underlying manifest/CSV
// export keeps full per-access-point detail, since an unexpected extra AP for a known SSID can
// itself be a signal worth seeing (e.g. a rogue/evil-twin AP), not just clutter to hide.
function groupWifiNetworksBySsid(networks) {
  const groups = new Map();
  for (const n of networks) {
    // A hidden SSID can't be meaningfully grouped with other hidden networks, so each one (keyed
    // by its own BSSID) stays its own row rather than collapsing unrelated networks together.
    const key = n.ssid || ` hidden:${n.bssid}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(n);
  }

  const strongestFirst = (a, b) => (b.signal ?? -Infinity) - (a.signal ?? -Infinity);
  const uniqueDefined = (values) => [...new Set(values.filter((v) => v != null))];

  return Array.from(groups.values()).map((group) => {
    const sorted = [...group].sort(strongestFirst);
    const strongest = sorted[0];
    const channels = uniqueDefined(group.map((n) => n.channel));
    const frequencies = uniqueDefined(group.map((n) => n.frequency));
    const result = {
      ssid: strongest.ssid,
      bssid: strongest.bssid,
      apCount: group.length,
      signal: strongest.signal,
      channel: channels.length === 1 ? channels[0] : channels.join(", "),
      frequency: frequencies.length === 1 ? frequencies[0] : frequencies.join(", "),
      security: strongest.security,
      in_use: group.some((n) => n.in_use),
    };
    // Provenance fields only exist on master-list (cross-scan) rows — combine them sensibly
    // across the group when present; a plain single-scan view's rows won't have them, so this is
    // a no-op there. times_seen is a max, not a sum: a single scan commonly sees the same SSID
    // on more than one band/AP at once, so summing each AP's own times_seen would double-count.
    if (group.some((n) => n.first_seen_at != null)) {
      result.first_seen_at = group.map((n) => n.first_seen_at).filter(Boolean).sort()[0];
      result.last_seen_at = group.map((n) => n.last_seen_at).filter(Boolean).sort().slice(-1)[0];
      result.times_seen = Math.max(...group.map((n) => n.times_seen || 0));
    }
    return result;
  });
}

// ---- Master list (aggregate) view --------------------------------------

async function renderAggregateView(siteId, scanType) {
  app.appendChild(el("p", {}, [el("a", { href: `#/site/${siteId}`, text: "← Back to site" })]));
  const title = scanType === "bluetooth_scan" ? "Bluetooth devices" : "WiFi networks";
  app.appendChild(el("h2", { text: `All ${title} seen at this site` }));
  app.appendChild(el("p", {
    class: "meta",
    text: "Merged across every completed scan of this type at this site.",
  }));

  let results = await api("GET", `/sites/${siteId}/aggregate/${scanType}`);
  if (!results.length) {
    app.appendChild(el("p", { class: "empty", text: "Nothing found yet — run a scan first." }));
    return;
  }

  if (scanType === "wifi_scan") {
    results = groupWifiNetworksBySsid(results);
  }

  const columns = (TABLE_COLUMNS[scanType] || []).concat([
    { label: "First Seen", render: (r) => r.first_seen_at || "" },
    { label: "Last Seen", render: (r) => r.last_seen_at || "" },
    { label: "Times Seen", render: (r) => (r.times_seen != null ? String(r.times_seen) : "") },
  ]);

  app.appendChild(renderTable(results, columns, { siteId }));
}

const COUNT_LABELS = {
  wifi_scan: "network(s) found",
  bluetooth_scan: "device(s) found",
  network_devices_scan: "device(s) found",
};

const EMPTY_LABELS = {
  wifi_scan: "No networks found.",
  bluetooth_scan: "No devices found.",
  network_devices_scan: "No devices found on this network.",
};

function scanDevicesButton(network, context) {
  if (!network.ssid) return "—"; // can't target a hidden/unnamed network by SSID
  return el("button", {
    class: "secondary",
    text: "Scan devices",
    onclick: async (e) => {
      e.target.disabled = true;
      try {
        const scan = await api("POST", `/sites/${context.siteId}/scans`, {
          scan_type: "network_devices_scan",
          params: { ssid: network.ssid, bssid: network.bssid },
        });
        location.hash = `#/site/${context.siteId}/scan/${scan.scan_id}`;
      } catch (err) {
        alert(`Couldn't start scan: ${err.message}`);
        e.target.disabled = false;
      }
    },
  });
}

const TABLE_COLUMNS = {
  wifi_scan: [
    { label: "SSID", render: (n) => n.ssid || "(hidden)" },
    { label: "BSSID", render: (n) => (n.apCount > 1 ? `${n.bssid} (+${n.apCount - 1} more)` : n.bssid || "") },
    { label: "Signal", render: (n) => (n.signal != null ? `${n.signal}%` : "") },
    { label: "Channel", render: (n) => (n.channel != null ? String(n.channel) : "") },
    { label: "Frequency", render: (n) => n.frequency || "" },
    { label: "Security", render: (n) => n.security || "Open" },
    { label: "In Use", render: (n) => (n.in_use ? "✓" : "") },
    { label: "", render: scanDevicesButton },
  ],
  bluetooth_scan: [
    { label: "Address", render: (d) => d.address || "" },
    { label: "Name", render: (d) => d.name || "(unnamed)" },
    { label: "Vendor", render: (d) => d.vendor || "" },
    { label: "RSSI", render: (d) => (d.rssi != null ? `${d.rssi} dBm` : "") },
    { label: "Manufacturer ID", render: (d) => (d.manufacturer_ids || []).join(", ") },
    { label: "Service UUIDs", render: (d) => (d.service_uuids || []).join(", ") },
  ],
  network_devices_scan: [
    { label: "IP", render: (d) => d.ip || "" },
    { label: "MAC", render: (d) => d.mac || "" },
    { label: "Vendor", render: (d) => d.vendor || "" },
    { label: "Hostname", render: (d) => d.hostname || "" },
  ],
};

function renderGallery(siteId, scanId, pages) {
  const gallery = el("div", { class: "gallery" });
  const images = pages.map((page) => ({
    src: `/sites/${siteId}/scans/${scanId}/artifacts/${page.screenshot_file}`,
    title: page.title || "(untitled)",
    url: page.url,
  }));

  images.forEach((image, index) => {
    const img = el("img", { src: image.src, alt: image.title, onclick: () => openLightbox(images, index) });
    const figure = el("figure", {}, [
      img,
      el("figcaption", {}, [
        el("span", { class: "title", text: image.title }),
        el("span", { class: "url", text: image.url }),
      ]),
    ]);
    gallery.appendChild(figure);
  });
  return gallery;
}

function renderTable(rows, columns, context = {}) {
  const table = el("table", { class: "network-table" });
  const headerRow = el("tr", {}, columns.map((c) => el("th", { text: c.label })));
  table.appendChild(el("thead", {}, [headerRow]));

  const tbody = el("tbody");
  for (const row of rows) {
    tbody.appendChild(el("tr", {}, columns.map((c) => {
      const value = c.render(row, context);
      return value instanceof Node ? el("td", {}, [value]) : el("td", { text: value });
    })));
  }
  table.appendChild(tbody);
  return table;
}

// `images` is the full gallery ([{src, title, url}, ...]) so Left/Right (or the on-screen ‹ ›
// buttons) can step through every screenshot without closing back out to the grid each time —
// only Escape / the × button / clicking the dimmed background closes it.
function openLightbox(images, startIndex) {
  let current = startIndex;

  const imgEl = el("img", { src: images[current].src, alt: images[current].title });
  const caption = el("div", { class: "lightbox-caption" });
  const stop = (fn) => (e) => { e.stopPropagation(); fn(); };

  function show(index) {
    current = (index + images.length) % images.length; // wraps around both ends
    const image = images[current];
    imgEl.src = image.src;
    imgEl.alt = image.title;
    caption.textContent = `${current + 1} / ${images.length} — ${image.title}`;
  }
  show(current);

  function close() {
    document.removeEventListener("keydown", onKeydown);
    overlay.remove();
  }

  function onKeydown(e) {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight") show(current + 1);
    else if (e.key === "ArrowLeft") show(current - 1);
  }

  const overlay = el("div", { class: "lightbox", onclick: close }, [
    el("button", { class: "lightbox-close", onclick: stop(close), text: "×" }),
    images.length > 1 && el("button", { class: "lightbox-nav lightbox-prev", onclick: stop(() => show(current - 1)), text: "‹" }),
    el("div", { class: "lightbox-content", onclick: (e) => e.stopPropagation() }, [imgEl, caption]),
    images.length > 1 && el("button", { class: "lightbox-nav lightbox-next", onclick: stop(() => show(current + 1)), text: "›" }),
  ].filter(Boolean));

  document.addEventListener("keydown", onKeydown);
  document.body.appendChild(overlay);
}
