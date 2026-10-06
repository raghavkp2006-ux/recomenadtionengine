import test from "node:test";
import assert from "node:assert/strict";
import {
  formatBadgeText,
  renderBadge,
  removeExistingBadge,
  showVerdictBadge,
} from "../src/content/verdict-badge.js";

function createMockDoc() {
  function findSelector(node, sel) {
    if (!node) return null;
    if (sel.startsWith("#")) {
      const id = sel.slice(1);
      if (node.id === id) return node;
    }
    if (sel.startsWith(".")) {
      const cls = sel.slice(1);
      if (node.className && node.className.split(" ").includes(cls)) return node;
    }
    if (node.tagName && node.tagName.toLowerCase() === sel.toLowerCase()) {
      return node;
    }
    for (const child of node.children || []) {
      const found = findSelector(child, sel);
      if (found) return found;
    }
    if (node.shadowRoot) {
      const found = findSelector(node.shadowRoot, sel);
      if (found) return found;
    }
    return null;
  }

  const doc = {
    createElement(tag) {
      const el = {
        tagName: tag.toUpperCase(),
        children: [],
        attributes: {},
        listeners: {},
        textContent: "",
        className: "",
        id: "",
        parentNode: null,
        setAttribute(k, v) { this.attributes[k] = v; },
        getAttribute(k) { return this.attributes[k]; },
        appendChild(child) {
          this.children.push(child);
          child.parentNode = this;
          return child;
        },
        addEventListener(event, fn) {
          this.listeners[event] = this.listeners[event] || [];
          this.listeners[event].push(fn);
        },
        dispatchEvent(event) {
          const type = typeof event === "string" ? event : event.type;
          const fns = this.listeners[type] || [];
          fns.forEach((fn) => fn(event));
        },
        remove() {
          if (this.parentNode) {
            const idx = this.parentNode.children.indexOf(this);
            if (idx >= 0) this.parentNode.children.splice(idx, 1);
          }
          if (doc.body) {
            const rootIdx = doc.body.children.indexOf(this);
            if (rootIdx >= 0) doc.body.children.splice(rootIdx, 1);
          }
        },
        attachShadow() {
          this.shadowRoot = {
            tagName: "SHADOW-ROOT",
            host: this,
            children: [],
            appendChild(child) {
              this.children.push(child);
              child.parentNode = this;
              return child;
            },
            querySelector(sel) {
              return findSelector(this, sel);
            },
          };
          return this.shadowRoot;
        },
        querySelector(sel) {
          return findSelector(this, sel);
        },
      };
      return el;
    },
    querySelector(sel) {
      return findSelector(this.body, sel);
    },
  };
  doc.body = doc.createElement("body");
  return doc;
}

test("formatBadgeText formats BUY verdict with fit and first reason", () => {
  const text = formatBadgeText({
    verdict: "BUY",
    fit: 0.88,
    reasons: [{ text: "Matches your anime vibe" }, { text: "Secondary reason" }],
  });
  assert.equal(text, "BUY · 88% fit · Matches your anime vibe");
});

test("formatBadgeText formats CONSIDER verdict with fit and first reason", () => {
  const text = formatBadgeText({
    verdict: "CONSIDER",
    fit: 0.62,
    reasons: [{ text: "Moderate colour affinity" }],
  });
  assert.equal(text, "CONSIDER · 62% fit · Moderate colour affinity");
});

test("formatBadgeText formats SKIP verdict with fit and reason", () => {
  const text = formatBadgeText({
    verdict: "SKIP",
    fit: 0.35,
    reasons: [{ text: "Price is outside your comfort range" }],
  });
  assert.equal(text, "SKIP · 35% fit · Price is outside your comfort range");
});

test("formatBadgeText formats status values for wishlist, cart, and purchase", () => {
  assert.equal(formatBadgeText({ status: "in_wishlist" }), "In your wishlist/cart");
  assert.equal(formatBadgeText({ status: "in_cart" }), "In your wishlist/cart");
  assert.equal(formatBadgeText({ status: "purchased" }), "Purchased");
});

test("formatBadgeText prefixes 'Early guess:' when confidence is low", () => {
  const text = formatBadgeText({
    verdict: "BUY",
    fit: 0.82,
    confidence: "low",
    reasons: [{ text: "Cool shirts" }],
  });
  assert.equal(text, "Early guess: BUY · 82% fit · Cool shirts");
});

test("formatBadgeText returns empty string for empty or missing verdict", () => {
  assert.equal(formatBadgeText(null), "");
  assert.equal(formatBadgeText({}), "");
  assert.equal(formatBadgeText({ verdict: null }), "");
});

test("XSS protection: reasons containing HTML/scripts render strictly as textContent", () => {
  const doc = createMockDoc();
  const malicious = '<img src=x onerror="alert(1)">';
  const text = formatBadgeText({
    verdict: "BUY",
    fit: 0.9,
    reasons: [{ text: malicious }],
  });
  assert.ok(text.includes(malicious));

  const host = renderBadge({ text, doc });
  assert.ok(host);

  const textNode = host.shadowRoot.querySelector(".badge-text");
  assert.ok(textNode);
  // textContent stores the literal string, not executed HTML tags
  assert.equal(textNode.textContent, `BUY · 90% fit · ${malicious}`);
  // No IMG tag should exist in the shadow root
  assert.equal(host.shadowRoot.querySelector("img"), null);
});

test("dedupe: repeated calls replace existing badge rather than stacking", () => {
  const doc = createMockDoc();
  renderBadge({ text: "BUY · 80% fit", doc });
  assert.equal(doc.body.children.length, 1);
  assert.equal(doc.querySelector("#polytaste-verdict-badge").shadowRoot.querySelector(".badge-text").textContent, "BUY · 80% fit");

  // Call again (e.g. SPA navigation or rapid updates)
  renderBadge({ text: "CONSIDER · 60% fit", doc });
  assert.equal(doc.body.children.length, 1, "Only 1 badge host must exist in document");
  assert.equal(doc.querySelector("#polytaste-verdict-badge").shadowRoot.querySelector(".badge-text").textContent, "CONSIDER · 60% fit");

  removeExistingBadge(doc);
  assert.equal(doc.body.children.length, 0);
});

test("401 path: renders 'Sign in to PolyTaste' pill and sends OPEN_LOGIN on click", async () => {
  const doc = createMockDoc();
  let loginMessageSent = false;

  // Mock chrome runtime
  globalThis.chrome = {
    runtime: {
      sendMessage(msg, callback) {
        if (msg.type === "GET_VERDICT") {
          callback({ ok: false, status: 401, error: "Not authenticated" });
        } else if (msg.type === "OPEN_LOGIN") {
          loginMessageSent = true;
          if (callback) callback({ ok: true });
        }
      },
    },
  };

  await showVerdictBadge({ product_id: "123" }, { enabled: true }, doc);

  const host = doc.querySelector("#polytaste-verdict-badge");
  assert.ok(host, "Badge host should be rendered on 401");
  const textNode = host.shadowRoot.querySelector(".badge-text");
  assert.equal(textNode.textContent, "Sign in to PolyTaste");

  const pill = host.shadowRoot.querySelector(".badge-pill");
  assert.ok(pill.className.includes("is-login"));

  // Trigger click
  pill.dispatchEvent({ type: "click", stopPropagation() {} });
  assert.equal(loginMessageSent, true, "Clicking 401 pill must send OPEN_LOGIN message");
});

test("non-401 failure: renders nothing and logs debug", async () => {
  const doc = createMockDoc();

  globalThis.chrome = {
    runtime: {
      sendMessage(msg, callback) {
        if (msg.type === "GET_VERDICT") {
          callback({ ok: false, status: 500, error: "Internal Server Error" });
        }
      },
    },
  };

  await showVerdictBadge({ product_id: "123" }, { enabled: true }, doc);
  assert.equal(doc.querySelector("#polytaste-verdict-badge"), null, "No badge should be rendered on 500 error");
});

test("disabled extension: renders nothing", async () => {
  const doc = createMockDoc();
  await showVerdictBadge({ product_id: "123" }, { enabled: false }, doc);
  assert.equal(doc.querySelector("#polytaste-verdict-badge"), null);
});
