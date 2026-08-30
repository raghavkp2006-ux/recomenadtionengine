import { getSyncState, updateSyncState } from "./local-store.js";

const QUEUE_KEY = "eventQueue";
export const MAX_QUEUE_SIZE = 1000;

async function readQueue() {
  const { [QUEUE_KEY]: queue } = await chrome.storage.local.get(QUEUE_KEY);
  return Array.isArray(queue) ? queue : [];
}

async function writeQueue(queue) {
  await chrome.storage.local.set({ [QUEUE_KEY]: queue });
  await updateSyncState({ pending: queue.length });
}

export async function enqueue(event) {
  const queue = await readQueue();
  const next = [...queue, event];
  const overflow = Math.max(0, next.length - MAX_QUEUE_SIZE);
  if (overflow) {
    const state = await getSyncState();
    await updateSyncState({ dropped: state.dropped + overflow });
  }
  await writeQueue(next.slice(overflow));
}

export async function peekBatch(size) {
  return (await readQueue()).slice(0, size);
}

export async function removeByEventIds(eventIds) {
  const removed = new Set(eventIds);
  await writeQueue((await readQueue()).filter((event) => !removed.has(event.event_id)));
}

export async function queueSize() {
  return (await readQueue()).length;
}

export async function nextRetryAt() {
  return (await getSyncState()).nextRetryAt || 0;
}
