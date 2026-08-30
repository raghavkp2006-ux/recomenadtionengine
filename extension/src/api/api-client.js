import { getSettings } from "../storage/local-store.js";

async function request(path, options = {}) {
  const { backendBaseUrl } = await getSettings();
  const url = `${backendBaseUrl.replace(/\/$/, "")}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || body?.detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

async function download(path, filename) {
  const { backendBaseUrl } = await getSettings();
  const response = await fetch(`${backendBaseUrl.replace(/\/$/, "")}${path}`, { credentials: "include" });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  await chrome.downloads.download({ url, filename, saveAs: true });
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const apiClient = {
  status: () => request("/myntra/events/status"),
  sendBatch: (events) => request("/myntra/events/batch", { method: "POST", body: JSON.stringify({ events }) }),
  connection: () => request("/myntra/connection"),
  updateConnection: (settings) => request("/myntra/connection", { method: "POST", body: JSON.stringify(settings) }),
  recommendations: () => request("/myntra/recommendations"),
  feedback: (product_id, feedback) => request("/myntra/feedback", { method: "POST", body: JSON.stringify({ product_id, feedback }) }),
  deleteData: () => request("/myntra/data", { method: "DELETE" }),
  exportCsv: () => download("/myntra/export.csv", "myntra-history.csv"),
};
