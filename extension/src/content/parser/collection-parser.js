import { PARSER_VERSION } from "./selectors.js";
import { parseProduct } from "./product-parser.js";

const text = (node) => node?.textContent?.trim() || null;
const number = (value) => {
  const found = String(value || "").replace(/,/g, "").match(/\d+(?:\.\d+)?/);
  return found ? Number(found[0]) : null;
};
const idFromUrl = (url) => String(url || "").match(/\/(\d{5,})(?:[/?#]|$)/)?.[1] || null;

function cards(document) {
  return [...document.querySelectorAll?.("[data-product-id], li[class*='item'], div[class*='item']") || []];
}

function productFromCard(card) {
  const link = card.querySelector?.("a[href]");
  const price = text(card.querySelector?.("[class*='price']"));
  return {
    platform: "myntra", product_id: card.getAttribute?.("data-product-id") || idFromUrl(link?.href),
    product_url: link?.href || null, brand: text(card.querySelector?.("[class*='brand']")),
    title: text(card.querySelector?.("[class*='name'], [class*='title']")), category: null, subcategory: null,
    gender: null, price: number(price), mrp: null, discount_percent: null, currency: "INR", rating: null,
    rating_count: null, colour: null, sizes: [], fit: null, material: null, pattern: null, occasion: null,
    season: null, seller: null, image_url: card.querySelector?.("img")?.src || null, attributes: {},
    source: "dom_or_structured_page_data", captured_at: new Date().toISOString(),
  };
}

function collection(document, kind) {
  try {
    const products = cards(document).map(productFromCard).filter((item) => item.product_id || item.title);
    return { products, parser_version: PARSER_VERSION, source: products.length ? "dom" : "unavailable", unsupported: !products.length, kind };
  } catch (error) {
    return { products: [], parser_version: PARSER_VERSION, source: "unavailable", unsupported: true, diagnostics: { error: error.message }, kind };
  }
}

export const parseWishlist = (document) => collection(document, "wishlist");
export const parseCart = (document) => collection(document, "cart");

export function parseOrders(document) {
  try {
    const orderNodes = [...document.querySelectorAll?.("[data-order-id], [class*='order']") || []];
    const orders = orderNodes.map((node) => ({
      order_id: node.getAttribute?.("data-order-id") || null,
      order_date: text(node.querySelector?.("time")) || null,
      status: text(node.querySelector?.("[class*='status']")) || null,
      items: [productFromCard(node)].filter((item) => item.product_id || item.title).map((item) => ({
        product_id: item.product_id, title: item.title, brand: item.brand, price: item.price, quantity: null, size: null, colour: null,
      })),
    })).filter((order) => order.order_id || order.items.length);
    return { orders, parser_version: PARSER_VERSION, source: orders.length ? "dom" : "unavailable", unsupported: !orders.length };
  } catch (error) {
    return { orders: [], parser_version: PARSER_VERSION, source: "unavailable", unsupported: true, diagnostics: { error: error.message } };
  }
}

export function parseAccessiblePage(document, pageType, pageUrl) {
  if (pageType === "wishlist") return parseWishlist(document);
  if (pageType === "cart") return parseCart(document);
  if (pageType === "orders") return parseOrders(document);
  return { product: parseProduct(document, pageUrl), parser_version: PARSER_VERSION };
}
