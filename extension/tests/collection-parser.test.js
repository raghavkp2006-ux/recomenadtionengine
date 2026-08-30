import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { parseCart, parseOrders, parseWishlist } from "../src/content/parser/collection-parser.js";

async function emptyFixture(name) {
  await readFile(new URL(`./fixtures/myntra/${name}`, import.meta.url), "utf8");
  return { querySelectorAll() { return []; } };
}

test("accessible collection parsers return unsupported instead of throwing on empty fixtures", async () => {
  assert.equal(parseWishlist(await emptyFixture("wishlist.html")).unsupported, true);
  assert.equal(parseCart(await emptyFixture("cart.html")).products.length, 0);
  assert.equal(parseOrders(await emptyFixture("orders.html")).orders.length, 0);
});
