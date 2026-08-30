export function isMyntraPage(url) { try { return new URL(url).hostname.endsWith("myntra.com"); } catch { return false; } }
export function getPageType(url) {
  const path = new URL(url).pathname.toLowerCase();
  if (/wishlist/.test(path)) return "wishlist";
  if (/cart|bag/.test(path)) return "cart";
  if (/order/.test(path)) return "orders";
  if (/search/.test(path)) return "search";
  if (/\/(?:[\w-]+\/){1,}\d{5,}(?:\/|$)/.test(path)) return "product";
  if (/\/[^/]+$/.test(path)) return "listing";
  return path === "/" ? "home" : "unknown";
}
export function extractProductId(url) { return String(url).match(/\/(\d{5,})(?:[/?#]|$)/)?.[1] || null; }
