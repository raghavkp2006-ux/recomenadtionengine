// MV3 content scripts are classic scripts. Dynamic imports keep parser modules
// testable without requiring a bundler or broad extension permissions.
(async () => {
const [{ getSettings }, { getPageType }, { parseProduct }, { parseSearch }, { parseListing }, { parseWishlist, parseCart, parseOrders }, { makeEvent }, { isDuplicate }] = await Promise.all([
  import("../storage/local-store.js"), import("./url.js"), import("./parser/product-parser.js"), import("./parser/search-parser.js"), import("./parser/listing-parser.js"), import("./parser/collection-parser.js"), import("./events/event-builder.js"), import("./events/event-deduplicator.js"),
]);
let lastSignature = "";
let timer;
let activeProduct = null;
function emit(event) { if (!isDuplicate(event)) chrome.runtime.sendMessage({ type: "MYNTRA_EVENT", event }); }
function dwellBucket(seconds) {
  if (seconds < 5) return "very_short";
  if (seconds < 20) return "short";
  if (seconds < 60) return "medium";
  if (seconds < 180) return "long";
  return "very_long";
}
function finishDwell() {
  if (!activeProduct) return;
  const seconds = Math.max(0, Math.round((Date.now() - activeProduct.startedAt) / 1000));
  emit(makeEvent("product_detail_view", { product: activeProduct.product, pageUrl: activeProduct.pageUrl, metadata: { dwell_seconds: seconds, dwell_bucket: dwellBucket(seconds) } }));
  if (seconds >= 60) emit(makeEvent("long_product_view", { product: activeProduct.product, pageUrl: activeProduct.pageUrl, metadata: { dwell_seconds: seconds, dwell_bucket: dwellBucket(seconds) } }));
  activeProduct = null;
}
async function renderRecommendations() {
  if (document.querySelector("#polytaste-myntra-panel")) return;
  try {
    const { recommendations } = await chrome.runtime.sendMessage({ type: "GET_RECOMMENDATIONS" });
    if (!recommendations?.length) return;
    const host = document.createElement("aside"); host.id = "polytaste-myntra-panel";
    host.attachShadow({ mode: "closed" }); const root = host.shadowRoot;
    root.innerHTML = `<style>:host{all:initial}section{position:fixed;right:16px;bottom:16px;width:260px;padding:14px;background:#fff;color:#282c3f;border-radius:12px;box-shadow:0 6px 24px #0003;font:13px Arial;z-index:2147483647}h2{font-size:15px;margin:0 0 8px}button{border:0;background:none;float:right;cursor:pointer}a{display:block;color:#282c3f;text-decoration:none;margin:7px 0}.price{color:#ff3f6c}</style><section><button aria-label="Dismiss recommendations">×</button><h2>✨ Recommended for you</h2><div></div></section>`;
    const list = root.querySelector("div"); recommendations.slice(0, 3).forEach((product) => { const link = document.createElement("a"); link.href = product.product_url || "#"; link.target = "_blank"; link.textContent = `${product.brand || ""} ${product.title || "Product"}${product.price != null ? ` · ₹${product.price}` : ""}`; link.addEventListener("click", () => emit(makeEvent("recommendation_click", { product }))); list.append(link); });
    root.querySelector("button").addEventListener("click", () => host.remove()); document.documentElement.append(host);
  } catch { /* a missing backend session must not alter Myntra */ }
}
async function inspectPage() {
  const settings = await getSettings(); if (!settings.enabled) return;
  const type = getPageType(location.href); const signature = `${type}|${location.href}|${document.title}`;
  if (signature === lastSignature) return; lastSignature = signature;
  if (activeProduct && activeProduct.pageUrl !== location.href) finishDwell();
  if (type === "product" && settings.collectProductViews && !activeProduct) { const product = parseProduct(document, location.href); activeProduct = { product, pageUrl: location.href, startedAt: Date.now() }; emit(makeEvent("product_view", { product })); renderRecommendations(); }
  if (type === "search" && settings.collectSearch) { const result = parseSearch(document, location.href); emit(makeEvent("search", { searchQuery: result.search_query })); }
  if (type === "listing" && settings.collectProductViews) emit(makeEvent("listing_view", { metadata: parseListing(document) }));
  if (type === "wishlist" && settings.collectWishlist) emit(makeEvent("order_view", { metadata: parseWishlist(document) }));
  if (type === "cart" && settings.collectCart) emit(makeEvent("cart_add", { metadata: parseCart(document) }));
  if (type === "orders" && settings.collectOrders) emit(makeEvent("order_view", { metadata: parseOrders(document) }));
}
function schedule() { clearTimeout(timer); timer = setTimeout(inspectPage, 350); }
getSettings().then((settings) => { if (settings.enabled) { new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true }); ["pushState", "replaceState"].forEach((method) => { const original = history[method]; history[method] = function (...args) { const value = original.apply(this, args); schedule(); return value; }; }); addEventListener("popstate", schedule); addEventListener("pagehide", finishDwell); schedule(); } });
})().catch(() => { /* parsing failures must never affect the host page */ });
