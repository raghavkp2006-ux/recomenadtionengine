export const DEFAULT_SETTINGS = Object.freeze({
  enabled: false,
  backendBaseUrl: "http://127.0.0.1:8000",
  collectProductViews: true,
  collectSearch: true,
  collectWishlist: true,
  collectCart: true,
  collectOrders: false,
  debug: false,
});

export async function getSettings() {
  try {
    if (!chrome?.runtime?.id) return { ...DEFAULT_SETTINGS };
    const { settings } = await chrome.storage.local.get("settings");
    return { ...DEFAULT_SETTINGS, ...(settings || {}) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export async function updateSettings(changes) {
  try {
    if (!chrome?.runtime?.id) return { ...DEFAULT_SETTINGS, ...changes };
    const next = { ...(await getSettings()), ...changes };
    await chrome.storage.local.set({ settings: next });
    return next;
  } catch {
    return { ...DEFAULT_SETTINGS, ...changes };
  }
}

export async function getSyncState() {
  try {
    if (!chrome?.runtime?.id) return { pending: 0, dropped: 0, lastSyncAt: null, lastError: null };
    const { syncState } = await chrome.storage.local.get("syncState");
    return { pending: 0, dropped: 0, lastSyncAt: null, lastError: null, ...(syncState || {}) };
  } catch {
    return { pending: 0, dropped: 0, lastSyncAt: null, lastError: null };
  }
}

export async function updateSyncState(changes) {
  try {
    if (!chrome?.runtime?.id) return { pending: 0, dropped: 0, lastSyncAt: null, lastError: null, ...changes };
    const next = { ...(await getSyncState()), ...changes };
    await chrome.storage.local.set({ syncState: next });
    return next;
  } catch {
    return { pending: 0, dropped: 0, lastSyncAt: null, lastError: null, ...changes };
  }
}
