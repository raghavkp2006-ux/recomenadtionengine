import { apiClient } from "../api/api-client.js";
import { getSettings, updateSyncState } from "../storage/local-store.js";
import { enqueue, peekBatch, removeByEventIds } from "../storage/queue.js";

const FLUSH_ALARM = "myntra-flush";
const BATCH_SIZE = 25;
const RETRIES = [5, 15, 30, 60, 300, 900];

async function syncQueue() {
  const settings = await getSettings();
  if (!settings.enabled) return;
  const state = await getSettings();
  const syncState = await chrome.storage.local.get("syncState");
  if (syncState.syncState?.nextRetryAt && Date.now() < syncState.syncState.nextRetryAt) return;
  const events = await peekBatch(BATCH_SIZE);
  if (!events.length) return;
  try {
    await apiClient.sendBatch(events);
    await removeByEventIds(events.map((event) => event.event_id));
    await updateSyncState({ lastSyncAt: new Date().toISOString(), lastError: null, retryCount: 0, nextRetryAt: 0 });
  } catch (error) {
    const current = syncState.syncState || {}; const retryCount = Math.min((current.retryCount || 0) + 1, RETRIES.length - 1);
    await updateSyncState({ lastError: error.message, retryCount, nextRetryAt: Date.now() + RETRIES[retryCount] * 1000 });
  }
}

chrome.runtime.onInstalled.addListener(() => chrome.alarms.create(FLUSH_ALARM, { periodInMinutes: 1 }));
chrome.runtime.onStartup.addListener(() => chrome.alarms.create(FLUSH_ALARM, { periodInMinutes: 1 }));
chrome.alarms.onAlarm.addListener((alarm) => { if (alarm.name === FLUSH_ALARM) syncQueue(); });

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "MYNTRA_EVENT") {
    enqueue(message.event).then(syncQueue).then(() => sendResponse({ ok: true })).catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message?.type === "SYNC_NOW") {
    syncQueue().then(() => sendResponse({ ok: true })).catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message?.type === "GET_RECOMMENDATIONS") {
    apiClient.recommendations().then((result) => sendResponse(result)).catch((error) => sendResponse({ recommendations: [], error: error.message }));
    return true;
  }
  return false;
});
