# Myntra end-to-end verification

1. Start the backend with `py main.py`, then sign in through the normal PolyTaste Google flow.
2. In Chrome, open `chrome://extensions`, enable Developer mode, select **Load unpacked**, and choose the `extension` directory.
3. Open the extension popup, set the backend URL under Settings, sign in, enable the integration, and grant the requested backend-host permission by selecting **Sync now**.
4. Visit a Myntra product page. Confirm one `product_view` appears in `/myntra/history`, and that the dismissible recommendation panel does not alter the host page.
5. Search and open a listing. Confirm search/listing events are emitted only for enabled categories.
6. Visit user-visible wishlist, cart, and orders pages. Confirm unavailable data is reported as unavailable rather than triggering a private API call.
7. Disable the backend temporarily, create activity, and confirm the popup shows pending events. Re-enable the backend and choose **Sync now**; the queue should drain without duplicate events.
8. Leave a product page after more than one minute. Confirm a `product_detail_view` contains dwell data and a `long_product_view` is generated.
9. Select **Export CSV** and verify UTF-8 quoted output. Select **Delete Myntra data**, confirm the dialog, and verify `/myntra/events/status` returns zero events.

Do not test with credentials, cookies, payment data, developer tools private endpoints, or automated login flows.
