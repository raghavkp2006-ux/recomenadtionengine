// Myntra DOM selectors are isolated here because the site markup is not a stable API.
export const SELECTORS = Object.freeze({
  product: {
    title: ["h1.pdp-name", "h1[class*='name']", "h1"],
    brand: ["h1.pdp-title", "[class*='brand']"],
    price: [".pdp-price strong", "[class*='price'] strong", "[class*='price']"],
    mrp: [".pdp-mrp s", "[class*='mrp']"],
    rating: [".index-overallRating", "[class*='rating']"],
    colour: [".pdp-color", "[class*='color']"],
    sizes: [".size-buttons-size-button", "[class*='size'] button"],
    image: [".image-grid-image img", "img[class*='image']"],
  },
});

export const PARSER_VERSION = "myntra-1";
