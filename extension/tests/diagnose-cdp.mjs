import { chromium } from "playwright";

async function main() {
  console.log("Connecting to Chrome over CDP on http://localhost:9222...");
  const browser = await chromium.connectOverCDP("http://localhost:9222");
  const contexts = browser.contexts();
  const context = contexts[0];
  if (!context) {
    throw new Error("No browser context found on CDP connection.");
  }

  const pages = context.pages();
  console.log(`Found ${pages.length} open tab(s):`);
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i];
    console.log(`  [${i}] ${p.url()} - ${await p.title().catch(() => "")}`);
  }

  // Find the Fashion dashboard page, or open it if not currently open
  let dashboardPage = pages.find(p => p.url().includes("polytaste-frontend.onrender.com") || p.url().includes("/myntra"));
  if (!dashboardPage) {
    console.log("Fashion dashboard tab not found among open tabs. Opening https://polytaste-frontend.onrender.com/myntra in a new tab...");
    dashboardPage = await context.newPage();
    await dashboardPage.goto("https://polytaste-frontend.onrender.com/myntra", { waitUntil: "domcontentloaded" });
    await dashboardPage.waitForTimeout(3000);
  } else {
    console.log("Using existing dashboard tab:", dashboardPage.url());
  }

  console.log("\n==================== STEP 1: FETCHING BACKEND STATE ====================");

  const endpoints = [
    { name: "/myntra/profile", url: "https://recomenadtionengine-api.onrender.com/myntra/profile" },
    { name: "/myntra/history", url: "https://recomenadtionengine-api.onrender.com/myntra/history" },
    { name: "/myntra/history/products", url: "https://recomenadtionengine-api.onrender.com/myntra/history/products" },
    { name: "/myntra/recommendations", url: "https://recomenadtionengine-api.onrender.com/myntra/recommendations" },
    { name: "/myntra/events/status", url: "https://recomenadtionengine-api.onrender.com/myntra/events/status" },
  ];

  for (const ep of endpoints) {
    console.log(`\n--- Fetching ${ep.name} ---`);
    try {
      const data = await dashboardPage.evaluate(async (url) => {
        const res = await fetch(url, { credentials: "include" });
        const json = await res.json().catch(() => null);
        return { status: res.status, ok: res.ok, data: json };
      }, ep.url);
      console.log(`HTTP ${data.status}:`, JSON.stringify(data.data, null, 2));
    } catch (err) {
      console.error(`Error fetching ${ep.name}:`, err.message);
    }
  }

  console.log("\n==================== CHECKING EXTENSION STORAGE ====================");
  const workers = context.serviceWorkers();
  console.log(`Found ${workers.length} active service worker(s)`);
  for (const w of workers) {
    console.log("  Worker URL:", w.url());
    if (w.url().includes("ehicjjjefimefanmlleacjhdmbfnobel") || w.url().includes("service-worker.js")) {
      const state = await w.evaluate(async () => {
        return chrome.storage.local.get(null);
      });
      console.log("  Storage content:", JSON.stringify(state, null, 2));
    }
  }

  // Disconnect CDP
  await browser.close();
  console.log("\nCDP session completed.");
}

main().catch(err => {
  console.error("CDP diagnostic script failed:", err);
  process.exit(1);
});
