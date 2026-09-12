import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const extensionPath = path.resolve(__dirname, "..");

async function main() {
  const context = await chromium.launchPersistentContext("", {
    headless: false,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
    ],
  });

  console.log("Waiting for extension service worker to register...");
  let [worker] = context.serviceWorkers();
  if (!worker) {
    worker = await context.waitForEvent("serviceworker", { timeout: 15000 });
  }
  const extensionId = worker.url().split("/")[2];
  console.log("Extension ID:", extensionId);

  await worker.evaluate(async () => {
    const { settings } = await chrome.storage.local.get("settings");
    await chrome.storage.local.set({
      settings: { ...(settings || {}), enabled: true, debug: true, backendBaseUrl: "https://recomenadtionengine-api.onrender.com" },
    });
  });
  console.log("Set enabled=true, debug=true in extension storage.");

  const page = await context.newPage();
  page.on("console", (msg) => console.log(`PAGE CONSOLE [${msg.type()}]:`, msg.text()));
  page.on("pageerror", (err) => console.log("PAGE ERROR:", err.message, err.stack));

  console.log("Navigating to Myntra listing...");
  await page.goto("https://www.myntra.com/shirts", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);

  const productLink = page.locator("a[href*='/buy']").first();
  await productLink.waitFor({ timeout: 15000 });
  const href = await productLink.getAttribute("href");
  const absoluteUrl = new URL(href, "https://www.myntra.com").toString();
  console.log("Navigating directly to product page:", absoluteUrl);

  await page.goto(absoluteUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  console.log("On product page, dwelling for 15s...");
  await page.waitForTimeout(15000);

  console.log("Final page URL:", page.url());
  console.log("Final page title:", await page.title());

  const queueState = await worker.evaluate(async () => {
    return chrome.storage.local.get(["eventQueue", "syncState"]);
  });
  console.log("Storage after dwell:", JSON.stringify(queueState, null, 2));

  console.log("Opening real popup page to trigger SYNC_NOW like a real click...");
  const popupPage = await context.newPage();
  await popupPage.goto(`chrome-extension://${extensionId}/src/popup/popup.html`);
  await popupPage.waitForTimeout(1000);

  const syncResult = await popupPage.evaluate(() => {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "SYNC_NOW" }, (response) => {
        resolve({ response, lastError: chrome.runtime.lastError?.message });
      });
    });
  });
  console.log("Sync result:", JSON.stringify(syncResult));

  await popupPage.waitForTimeout(2000);
  const finalState = await worker.evaluate(async () => {
    return chrome.storage.local.get(["eventQueue", "syncState"]);
  });
  console.log("Final storage state:", JSON.stringify(finalState, null, 2));

  await context.close();
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
