# PolyTaste for Myntra extension

This Manifest V3 extension is deliberately user-controlled. It requests storage, alarms, downloads (only after the user chooses **Export CSV**), and Myntra page access. It does not read cookies, credentials, payment details, session secrets, or private Myntra APIs.

## Local development

1. Start the PolyTaste backend at `http://localhost:8000`.
2. In Chrome, open `chrome://extensions`, enable **Developer mode**, then choose **Load unpacked**.
3. Select this `extension/` directory.
4. Open the extension settings, confirm the backend URL, and sign in through the normal PolyTaste login page.
5. Enable the integration and choose **Sync now** once to grant the declared local-backend permission. The extension observes only the collection categories you enable and queues failed uploads locally for retry.

The development manifest declares `http://localhost:8000/*` as an optional backend host. A production build must replace/add the exact deployed PolyTaste API origin; it must never use `<all_urls>`.

The page panel asks the extension service worker for recommendations, so backend access uses the origin the user explicitly granted from the popup rather than relying on the host page's network context.

Run the extension unit tests with `npm test`.

For browser-level validation, follow `../docs/myntra-e2e-checklist.md`.
