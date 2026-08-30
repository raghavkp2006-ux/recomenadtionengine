import { PARSER_VERSION, SELECTORS } from "./selectors.js";

const emptyProduct = () => ({
  platform: "myntra", product_id: null, product_url: null, brand: null, title: null,
  category: null, subcategory: null, gender: null, price: null, mrp: null,
  discount_percent: null, currency: "INR", rating: null, rating_count: null,
  colour: null, sizes: [], fit: null, material: null, pattern: null, occasion: null,
  season: null, seller: null, image_url: null, attributes: {},
  source: "dom_or_structured_page_data", captured_at: null,
});

function text(node) { return node?.textContent?.trim() || null; }
function number(value) {
  if (!value) return null;
  const match = String(value).replace(/,/g, "").match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}
function firstText(document, selectors) {
  for (const selector of selectors) {
    const value = text(document.querySelector(selector));
    if (value) return value;
  }
  return null;
}
function firstImage(document, selectors) {
  for (const selector of selectors) {
    const src = document.querySelector(selector)?.getAttribute?.("src");
    if (src) return src;
  }
  return null;
}
function productIdFromUrl(url) {
  if (!url) return null;
  const match = url.match(/\/(\d{5,})(?:[/?#]|$)/);
  return match?.[1] || null;
}

function productJsonLd(document) {
  const scripts = document.querySelectorAll?.('script[type="application/ld+json"]') || [];
  for (const script of scripts) {
    try {
      const data = JSON.parse(script.textContent);
      const graphEntries = Array.isArray(data?.["@graph"]) ? data["@graph"] : [];
      const entries = Array.isArray(data) ? data : [data, ...graphEntries];
      const product = entries.find((item) => item?.["@type"] === "Product" || item?.["@type"]?.includes?.("Product"));
      if (product) return product;
    } catch { /* malformed structured data is non-fatal */ }
  }
  return null;
}

export function parseProductWithDiagnostics(document, pageUrl = globalThis.location?.href || null) {
  const product = emptyProduct();
  const diagnostics = { parser_version: PARSER_VERSION, fields: {}, structured_data_found: false };
  try {
    const jsonLd = productJsonLd(document);
    diagnostics.structured_data_found = Boolean(jsonLd);
    const offers = Array.isArray(jsonLd?.offers) ? jsonLd.offers[0] : jsonLd?.offers;
    const selector = SELECTORS.product;
    product.product_url = pageUrl;
    product.product_id = jsonLd?.sku || jsonLd?.productID || productIdFromUrl(pageUrl);
    product.title = jsonLd?.name || firstText(document, selector.title);
    product.brand = jsonLd?.brand?.name || jsonLd?.brand || firstText(document, selector.brand);
    product.price = number(offers?.price) ?? number(firstText(document, selector.price));
    product.mrp = number(offers?.highPrice) ?? number(firstText(document, selector.mrp));
    product.rating = number(jsonLd?.aggregateRating?.ratingValue) ?? number(firstText(document, selector.rating));
    product.rating_count = number(jsonLd?.aggregateRating?.ratingCount);
    product.image_url = (Array.isArray(jsonLd?.image) ? jsonLd.image[0] : jsonLd?.image) || firstImage(document, selector.image);
    product.colour = firstText(document, selector.colour);
    product.sizes = [...(document.querySelectorAll?.(selector.sizes.join(",")) || [])].map(text).filter(Boolean);
    product.discount_percent = product.price && product.mrp && product.mrp > product.price
      ? Math.round(((product.mrp - product.price) / product.mrp) * 10000) / 100 : null;
    product.captured_at = new Date().toISOString();
    for (const [key, value] of Object.entries(product)) if (value !== null && value !== "" && (!Array.isArray(value) || value.length)) diagnostics.fields[key] = jsonLd ? "structured_data_or_dom" : "dom";
  } catch (error) {
    diagnostics.error = error instanceof Error ? error.message : "unknown parser error";
  }
  return { product, diagnostics };
}

export function parseProduct(document, pageUrl) {
  return parseProductWithDiagnostics(document, pageUrl).product;
}
