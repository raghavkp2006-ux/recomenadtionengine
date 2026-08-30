const WINDOWS = { product_view: 30_000, listing_view: 30_000, search: 10_000, product_click: 2_000 };
const seen = new Map();
export function isDuplicate(event, now = Date.now()) {
  const key = [event.event_type, event.product?.product_id || "", event.page_url || "", event.search_query || ""].join("|");
  const previous = seen.get(key); const windowMs = WINDOWS[event.event_type] ?? 10_000;
  seen.set(key, now);
  for (const [candidate, timestamp] of seen) if (now - timestamp > 60_000) seen.delete(candidate);
  return previous != null && now - previous < windowMs;
}
