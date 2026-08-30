import { getSettings } from "../storage/local-store.js";

// The extension never reads or persists backend cookies. Authentication happens
// in a normal backend page; a dedicated, revocable extension handoff is added later.
export async function openBackendLogin() {
  const { backendBaseUrl } = await getSettings();
  await chrome.tabs.create({ url: `${backendBaseUrl.replace(/\/$/, "")}/auth/google/login` });
}
