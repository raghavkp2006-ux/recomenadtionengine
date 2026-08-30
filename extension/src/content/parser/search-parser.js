import { PARSER_VERSION } from "./selectors.js";

const SEARCH_PARAMS = ["rawQuery", "query", "q", "search"];

export function parseSearch(document, pageUrl = globalThis.location?.href || "") {
  let searchQuery = null;
  try {
    const url = new URL(pageUrl);
    searchQuery = SEARCH_PARAMS.map((key) => url.searchParams.get(key)).find(Boolean) || null;
  } catch { /* URL data is optional */ }
  if (!searchQuery) {
    const input = document.querySelector?.("input[type='search'], input[placeholder*='Search'], input[class*='search']");
    searchQuery = input?.value?.trim() || null;
  }
  return { search_query: searchQuery, parser_version: PARSER_VERSION, source: searchQuery ? "url_or_dom" : "unavailable" };
}
