import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { parseProduct, parseProductWithDiagnostics } from "../src/content/parser/product-parser.js";

async function fixtureDocument(name) {
  const html = await readFile(new URL(`./fixtures/myntra/${name}`, import.meta.url), "utf8");
  const scripts = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((match) => ({ textContent: match[1] }));
  return { querySelectorAll(selector) { return selector === 'script[type="application/ld+json"]' ? scripts : []; }, querySelector() { return null; } };
}

test("product parser prefers fixture JSON-LD and normalizes price fields", async () => {
  const product = parseProduct(await fixtureDocument("product-basic.html"), "https://www.myntra.com/shirts/roadster/12345678/buy");
  assert.equal(product.product_id, "12345678");
  assert.equal(product.brand, "Roadster");
  assert.equal(product.price, 1299);
  assert.equal(product.mrp, 1999);
  assert.equal(product.discount_percent, 35.02);
  assert.equal(product.rating_count, 145);
});

test("missing page fields are null rather than parser failures", async () => {
  const result = parseProductWithDiagnostics(await fixtureDocument("product-missing-price.html"), "https://www.myntra.com/tees/basic/87654321/buy");
  assert.equal(result.product.price, null);
  assert.equal(result.product.mrp, null);
  assert.equal(result.product.rating, null);
  assert.equal(result.product.title, "Basic Tee");
  assert.equal(result.diagnostics.structured_data_found, true);
});
