import { PARSER_VERSION } from "./selectors.js";

function number(value) { const match = String(value || "").replace(/,/g, "").match(/\d+(?:\.\d+)?/); return match ? Number(match[0]) : null; }
function emptyProduct() { return { platform: "myntra", product_id: null, product_url: null, brand: null, title: null, category: null, subcategory: null, gender: null, price: null, mrp: null, discount_percent: null, currency: "INR", rating: null, rating_count: null, colour: null, sizes: [], fit: null, material: null, pattern: null, occasion: null, season: null, seller: null, image_url: null, attributes: {}, source: "dom_or_structured_page_data", captured_at: new Date().toISOString() }; }

export function parseListing(document) {
  const products = [];
  for (const script of document.querySelectorAll?.('script[type="application/ld+json"]') || []) {
    try {
      const data = JSON.parse(script.textContent);
      for (const entry of Array.isArray(data?.itemListElement) ? data.itemListElement : []) {
        const value = entry.item || entry;
        if (!value || (value["@type"] && value["@type"] !== "Product")) continue;
        const offers = Array.isArray(value.offers) ? value.offers[0] : value.offers;
        const product = emptyProduct();
        product.product_id = value.sku || value.productID || null;
        product.product_url = value.url || null;
        product.title = value.name || null;
        product.brand = value.brand?.name || value.brand || null;
        product.price = number(offers?.price);
        product.mrp = number(offers?.highPrice);
        product.image_url = Array.isArray(value.image) ? value.image[0] : value.image || null;
        product.rating = number(value.aggregateRating?.ratingValue);
        product.rating_count = number(value.aggregateRating?.ratingCount);
        product.discount_percent = product.price && product.mrp && product.mrp > product.price ? Math.round(((product.mrp - product.price) / product.mrp) * 10000) / 100 : null;
        products.push(product);
      }
    } catch { /* malformed page data is ignored */ }
  }
  return { products, parser_version: PARSER_VERSION, source: products.length ? "structured_data" : "unavailable" };
}
