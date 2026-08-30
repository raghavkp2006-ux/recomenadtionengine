import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { parseListing } from "../src/content/parser/listing-parser.js";
import { parseSearch } from "../src/content/parser/search-parser.js";

async function documentFromFixture(name) {
  const html = await readFile(new URL(`./fixtures/myntra/${name}`, import.meta.url), "utf8");
  const scripts = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((match) => ({ textContent: match[1] }));
  const input = html.match(/<input type="search" value="([^"]*)"/);
  return {
    querySelectorAll(selector) { return selector === 'script[type="application/ld+json"]' ? scripts : []; },
    querySelector(selector) { return selector.includes("input") && input ? { value: input[1] } : null; },
  };
}

test("listing parser extracts normalized products from an ItemList fixture", async () => {
  const listing = parseListing(await documentFromFixture("listing.html"));
  assert.equal(listing.products.length, 2);
  assert.equal(listing.products[0].product_id, "11111");
  assert.equal(listing.products[0].discount_percent, 33.36);
  assert.equal(listing.products[1].mrp, null);
});

test("search parser uses URL query first then a visible input", async () => {
  const document = await documentFromFixture("search.html");
  assert.equal(parseSearch(document, "https://www.myntra.com/men?rawQuery=oversized%20tee").search_query, "oversized tee");
  assert.equal(parseSearch(document, "https://www.myntra.com/men").search_query, "linen shirts");
});
