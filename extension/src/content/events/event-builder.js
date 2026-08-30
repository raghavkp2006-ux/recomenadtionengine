import { PARSER_VERSION } from "../parser/selectors.js";

export function makeEvent(eventType, { product = null, searchQuery = null, metadata = {}, pageUrl = location.href } = {}) {
  return {
    event_id: crypto.randomUUID(), platform: "myntra", event_type: eventType,
    occurred_at: new Date().toISOString(), page_url: pageUrl, product, search_query: searchQuery,
    metadata, extension_version: chrome.runtime.getManifest().version, parser_version: PARSER_VERSION,
  };
}
