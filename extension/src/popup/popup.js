import { openBackendLogin } from "../api/auth-client.js";
import { getSettings, getSyncState, updateSettings } from "../storage/local-store.js";
import { apiClient } from "../api/api-client.js";

const fields = ["enabled", "collectProductViews", "collectSearch", "collectWishlist", "collectCart", "collectOrders"];
const status = document.querySelector("#status");
let currentSettings = null;

async function render() {
  const settings = await getSettings();
  currentSettings = settings;
  const syncState = await getSyncState();
  fields.forEach((name) => { document.querySelector(`#${name}`).checked = settings[name]; });
  document.querySelector("#pending").textContent = `Events pending: ${syncState.pending}`;
  const origin = new URL(settings.backendBaseUrl).origin;
  const hasPermission = await chrome.permissions.contains({ origins: [`${origin}/*`] });
  if (!hasPermission) {
    status.textContent = "Backend permission not granted yet — click Sync once to enable automatic syncing.";
  } else {
    status.textContent = syncState.lastError ? `Connection: ${syncState.lastError}` : `Last sync: ${syncState.lastSyncAt || "Not yet"}`;
  }
}

const connectionPayload = (settings) => ({
  enabled: settings.enabled, collect_product_views: settings.collectProductViews,
  collect_search: settings.collectSearch, collect_wishlist: settings.collectWishlist,
  collect_cart: settings.collectCart, collect_orders: settings.collectOrders,
});
fields.forEach((name) => document.querySelector(`#${name}`).addEventListener("change", async (event) => {
  const settings = await updateSettings({ [name]: event.target.checked });
  try { await apiClient.updateConnection(connectionPayload(settings)); }
  catch (error) { status.textContent = `Saved locally; backend update failed: ${error.message}`; }
  render();
}));
document.querySelector("#sync").addEventListener("click", (clickEvent) => {
  const origin = new URL(currentSettings.backendBaseUrl).origin;
  chrome.permissions.request({ origins: [`${origin}/*`] }, (granted) => {
    if (!granted) {
      status.textContent = "Connection permission was not granted.";
      return;
    }
    chrome.runtime.sendMessage({ type: "SYNC_NOW" }, render);
  });
});
document.querySelector("#login").addEventListener("click", openBackendLogin);
document.querySelector("#export").addEventListener("click", async () => {
  try { await apiClient.exportCsv(); status.textContent = "CSV download started."; }
  catch (error) { status.textContent = error.message; }
});
document.querySelector("#delete").addEventListener("click", async () => {
  if (!confirm("Delete all Myntra activity stored for this account?")) return;
  try { await apiClient.deleteData(); await chrome.storage.local.remove(["eventQueue", "syncState"]); status.textContent = "Myntra data deleted."; render(); }
  catch (error) { status.textContent = error.message; }
});
render();
