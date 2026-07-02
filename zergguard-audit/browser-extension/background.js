// ZergGuard URL Shield — background service worker.
// Loads the local IOC cache (synced via a periodic fetch from a local file
// server you'd run on localhost, OR via chrome.storage updates pushed by
// a separate Mac process). Intercepts main-frame navigation and blocks
// when destination matches a known-bad domain.

const STORAGE_KEY = "zergguard_iocs";
const LOCAL_IOC_URL = "http://127.0.0.1:54321/ioc.json"; // optional local server

async function loadIocList() {
  // Prefer chrome.storage if populated; fallback to local server fetch.
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  if (stored[STORAGE_KEY]?.domains?.length) {
    return stored[STORAGE_KEY].domains;
  }
  try {
    const r = await fetch(LOCAL_IOC_URL, { cache: "no-store" });
    const j = await r.json();
    await chrome.storage.local.set({ [STORAGE_KEY]: j });
    return j.domains || [];
  } catch {
    return [];
  }
}

function hostInList(url, domains) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return domains.find(d => host === d || host.endsWith("." + d));
  } catch {
    return null;
  }
}

chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return; // main frame only
  const domains = await loadIocList();
  const hit = hostInList(details.url, domains);
  if (hit) {
    // Redirect to a local warning page
    const block = chrome.runtime.getURL("blocked.html") +
      `?url=${encodeURIComponent(details.url)}&hit=${encodeURIComponent(hit)}`;
    chrome.tabs.update(details.tabId, { url: block });
  }
});

// Refresh IOC list daily
chrome.alarms.create("ioc-refresh", { periodInMinutes: 60 * 24 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "ioc-refresh") {
    await chrome.storage.local.remove(STORAGE_KEY);
    await loadIocList();
  }
});
