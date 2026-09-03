const app = document.getElementById("app");

const SCAN_TYPES = [
  { value: "router_screenshot", label: "Router Screenshot" },
  { value: "wifi_scan", label: "WiFi Scan" },
  // bluetooth_scan will be added here once its runner exists server-side.
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
  } catch (err) {
    app.appendChild(el("div", { class: "error-box", text: err.message }));
  }
}

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", render);

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
}

function buildNewScanForm(siteId) {
  const form = el("div");

  const typeSelect = el("select", {}, SCAN_TYPES.map((t) => el("option", { value: t.value, text: t.label })));
  form.appendChild(el("label", { text: "Scan type" }));
  form.appendChild(typeSelect);

  const routerFields = el("div");
  const wifiFields = el("div");
  form.appendChild(routerFields);
  form.appendChild(wifiFields);

  const syncFieldVisibility = () => {
    const isWifi = typeSelect.value === "wifi_scan";
    routerFields.style.display = isWifi ? "none" : "";
    wifiFields.style.display = isWifi ? "" : "none";
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
  const clickNav = el("input", { type: "checkbox" });

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
      " Also explore nav/sidebar buttons, not just links (for admin UIs whose settings pages" +
      " aren't real links) — still never clicks anything labeled like a destructive action, and" +
      " blocks all non-GET requests during exploration as a hard backstop"
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
        } else {
          params = {
            router_url: routerUrl.value.trim(),
            auth_type: authSelect.value,
            username: username.value,
            password: password.value,
            max_pages: Number(maxPages.value) || 200,
          };
          if (usernameSel.value.trim()) params.username_selector = usernameSel.value.trim();
          if (passwordSel.value.trim()) params.password_selector = passwordSel.value.trim();
          if (submitSel.value.trim()) params.submit_selector = submitSel.value.trim();
          if (clickNav.checked) params.click_nav = true;
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

  const countLabel = scan.scan_type === "wifi_scan" ? "network(s) found" : "page(s) captured";
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

  const results = await api("GET", `/sites/${siteId}/scans/${scanId}/results`);
  if (!results.length) {
    app.appendChild(el("p", { class: "empty", text: scan.scan_type === "wifi_scan" ? "No networks found." : "No pages captured." }));
    return;
  }

  if (scan.scan_type === "wifi_scan") {
    app.appendChild(renderNetworkTable(results));
  } else {
    app.appendChild(renderGallery(siteId, scanId, results));
  }
}

function renderGallery(siteId, scanId, pages) {
  const gallery = el("div", { class: "gallery" });
  for (const page of pages) {
    const src = `/sites/${siteId}/scans/${scanId}/artifacts/${page.screenshot_file}`;
    const img = el("img", { src, alt: page.title || page.url, onclick: () => openLightbox(src) });
    const figure = el("figure", {}, [
      img,
      el("figcaption", {}, [
        el("span", { class: "title", text: page.title || "(untitled)" }),
        el("span", { class: "url", text: page.url }),
      ]),
    ]);
    gallery.appendChild(figure);
  }
  return gallery;
}

function renderNetworkTable(networks) {
  const table = el("table", { class: "network-table" });
  const headerRow = el("tr", {}, [
    "SSID", "BSSID", "Signal", "Channel", "Frequency", "Security", "In Use",
  ].map((label) => el("th", { text: label })));
  table.appendChild(el("thead", {}, [headerRow]));

  const tbody = el("tbody");
  for (const n of networks) {
    tbody.appendChild(el("tr", {}, [
      el("td", { text: n.ssid || "(hidden)" }),
      el("td", { text: n.bssid || "" }),
      el("td", { text: n.signal != null ? `${n.signal}%` : "" }),
      el("td", { text: n.channel != null ? String(n.channel) : "" }),
      el("td", { text: n.frequency || "" }),
      el("td", { text: n.security || "Open" }),
      el("td", { text: n.in_use ? "✓" : "" }),
    ]));
  }
  table.appendChild(tbody);
  return table;
}

function openLightbox(src) {
  const overlay = el("div", { class: "lightbox", onclick: () => overlay.remove() }, [el("img", { src })]);
  document.body.appendChild(overlay);
}
