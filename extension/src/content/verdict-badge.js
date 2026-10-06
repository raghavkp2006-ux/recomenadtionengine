// Verdict badge rendered in a Shadow DOM host on Myntra product pages.
// Uses textContent strictly to prevent XSS.

export function formatBadgeText(data) {
  if (!data) return "";
  if (data.status === "in_wishlist" || data.status === "in_cart") {
    return "In your wishlist/cart";
  }
  if (data.status === "purchased") {
    return "Purchased";
  }

  let text = "";
  if (data.verdict) {
    text = String(data.verdict).toUpperCase();
    if (data.fit != null) {
      const fitNum = Number(data.fit);
      const fitPct = fitNum <= 1 ? Math.round(fitNum * 100) : Math.round(fitNum);
      text += ` · ${fitPct}% fit`;
    }
    const firstReason = data.reasons?.[0]?.text || (typeof data.reasons?.[0] === "string" ? data.reasons[0] : "");
    if (firstReason) {
      text += ` · ${firstReason}`;
    }
  }

  if (!text) return "";

  if (data.confidence === "low") {
    text = `Early guess: ${text}`;
  }
  return text;
}

export function removeExistingBadge(doc = (typeof document !== "undefined" ? document : null)) {
  if (!doc) return;
  const existing = doc.querySelector("#polytaste-verdict-badge");
  if (existing) {
    existing.remove();
  }
}

export function renderBadge({
  text,
  isLogin = false,
  verdict = null,
  doc = (typeof document !== "undefined" ? document : null),
  onLogin = null,
  onDismiss = null,
} = {}) {
  if (!doc || !text) return null;
  removeExistingBadge(doc);

  const host = doc.createElement("aside");
  host.id = "polytaste-verdict-badge";
  const root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  const style = doc.createElement("style");
  style.textContent = `
    :host { all: initial; }
    .badge-pill {
      position: fixed;
      right: 20px;
      bottom: 20px;
      z-index: 2147483647;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 16px;
      background: #18181b;
      color: #fafafa;
      border: 1px solid #27272a;
      border-radius: 9999px;
      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 13px;
      line-height: 1.4;
      max-width: 480px;
    }
    .badge-pill.is-login {
      cursor: pointer;
      background: #27272a;
      border-color: #3f3f46;
    }
    .badge-pill.is-login:hover {
      background: #3f3f46;
    }
    .badge-text {
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .dismiss-btn {
      background: none;
      border: none;
      color: #a1a1aa;
      font-size: 16px;
      line-height: 1;
      padding: 2px 4px;
      margin-left: 2px;
      cursor: pointer;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .dismiss-btn:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.1);
    }
  `;

  const pill = doc.createElement("div");
  pill.className = isLogin ? "badge-pill is-login" : "badge-pill";

  const textSpan = doc.createElement("span");
  textSpan.className = "badge-text";
  // CRITICAL SECURITY RULE: textContent only, never innerHTML
  textSpan.textContent = text;
  pill.appendChild(textSpan);

  if (isLogin) {
    pill.addEventListener("click", () => {
      if (typeof onLogin === "function") {
        onLogin();
      } else if (typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
        chrome.runtime.sendMessage({ type: "OPEN_LOGIN" });
      }
    });
  }

  const dismissBtn = doc.createElement("button");
  dismissBtn.className = "dismiss-btn";
  dismissBtn.setAttribute("aria-label", "Dismiss verdict");
  dismissBtn.textContent = "×";
  dismissBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    host.remove();
    if (typeof onDismiss === "function") {
      onDismiss();
    }
  });
  pill.appendChild(dismissBtn);

  root.appendChild(style);
  root.appendChild(pill);

  const container = doc.body || doc.documentElement || doc;
  if (container && container.appendChild) {
    container.appendChild(host);
  }
  return host;
}

export function requestVerdict(product, timeoutMs = 4000) {
  return new Promise((resolve, reject) => {
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      reject(new Error("Timeout waiting for verdict"));
    }, timeoutMs);

    try {
      if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) {
        clearTimeout(timer);
        return reject(new Error("chrome.runtime unavailable"));
      }

      chrome.runtime.sendMessage({ type: "GET_VERDICT", product }, (response) => {
        if (timedOut) return;
        clearTimeout(timer);
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    } catch (err) {
      if (!timedOut) {
        clearTimeout(timer);
        reject(err);
      }
    }
  });
}

export async function showVerdictBadge(product, settings, doc = (typeof document !== "undefined" ? document : null)) {
  if (!settings?.enabled) {
    return;
  }
  if (!doc) return;

  // SPA navigation must replace, not stack
  removeExistingBadge(doc);

  try {
    const response = await requestVerdict(product, 4000);
    if (!response) {
      console.debug("[PolyTaste] Verdict response empty");
      return;
    }

    if (!response.ok) {
      if (
        response.status === 401 ||
        (response.error && (response.error.includes("401") || response.error.toLowerCase().includes("not authenticated")))
      ) {
        renderBadge({
          text: "Sign in to PolyTaste",
          isLogin: true,
          doc,
        });
        return;
      }
      console.debug("[PolyTaste] Verdict request failed:", response.error);
      return;
    }

    const verdictData = response.verdict;
    const badgeText = formatBadgeText(verdictData);
    if (badgeText) {
      renderBadge({
        text: badgeText,
        verdict: verdictData?.verdict,
        doc,
      });
    }
  } catch (error) {
    if (error?.status === 401 || error?.message?.includes("401")) {
      renderBadge({
        text: "Sign in to PolyTaste",
        isLogin: true,
        doc,
      });
      return;
    }
    console.debug("[PolyTaste] Verdict badge error:", error?.message || error);
  }
}
