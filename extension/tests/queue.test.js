import test from "node:test";
import assert from "node:assert/strict";

const storage = {};
globalThis.chrome = { storage: { local: {
  async get(key) { return typeof key === "string" ? { [key]: storage[key] } : storage; },
  async set(values) { Object.assign(storage, values); },
} } };

const { enqueue, peekBatch, removeByEventIds, queueSize } = await import("../src/storage/queue.js");

test("queue retains events until their IDs are acknowledged", async () => {
  storage.eventQueue = [];
  await enqueue({ event_id: "one" });
  await enqueue({ event_id: "two" });
  assert.equal(await queueSize(), 2);
  assert.deepEqual(await peekBatch(1), [{ event_id: "one" }]);
  await removeByEventIds(["one"]);
  assert.deepEqual(await peekBatch(5), [{ event_id: "two" }]);
});
