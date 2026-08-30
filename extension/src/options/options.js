import { getSettings, updateSettings } from "../storage/local-store.js";

const url = document.querySelector("#backendBaseUrl");
const debug = document.querySelector("#debug");
const result = document.querySelector("#result");

getSettings().then((settings) => { url.value = settings.backendBaseUrl; debug.checked = settings.debug; });
document.querySelector("#save").addEventListener("click", async () => {
  try { new URL(url.value); await updateSettings({ backendBaseUrl: url.value, debug: debug.checked }); result.textContent = "Settings saved."; }
  catch { result.textContent = "Enter a valid backend URL."; }
});
