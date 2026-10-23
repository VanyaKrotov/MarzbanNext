import assert from "node:assert/strict";
import { test } from "node:test";
import { fetchAllPages } from "../src/service/pagination";

test("pagination keeps server order and stops if the collection shrinks between requests", async () => {
  const offsets: number[] = [];
  const result = await fetchAllPages(async (offset) => {
    offsets.push(offset);
    return offset === 0 ? { items: [3, 1], total: 4 } : { items: [], total: 1 };
  });
  assert.deepEqual(result, [3, 1]);
  assert.deepEqual(offsets, [0, 2]);
});

test("pagination propagates page failures instead of returning partial data", async () => {
  const failure = new Error("aborted request");
  await assert.rejects(
    fetchAllPages(async (offset) => {
      if (offset) throw failure;
      return { items: [1], total: 2 };
    }),
    failure,
  );
});
