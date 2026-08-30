export const DEFAULT_SETTINGS = Object.freeze({
  enabled: false,
  backendBaseUrl: "http://localhost:8000",
  collectProductViews: true,
  collectSearch: true,
  collectWishlist: true,
  collectCart: true,
  collectOrders: false,
  debug: false,
});

export async function getSettings() {
  const { settings } = await chrome.storage.local.get("settings");
  return { ...DEFAULT_SETTINGS, ...(settings || {}) };
}

export async function updateSettings(changes) {
  const next = { ...(await getSettings()), ...changes };
  await chrome.storage.local.set({ settings: next });
  return next;
}

export async function getSyncState() {
  const { syncState } = await chrome.storage.local.get("syncState");
  return { pending: 0, dropped: 0, lastSyncAt: null, lastError: null, ...(syncState || {}) };
}

export async function updateSyncState(changes) {
  const next = { ...(await getSyncState()), ...changes };
  await chrome.storage.local.set({ syncState: next });
  return next;
}
