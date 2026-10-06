import assert from "node:assert/strict";
import { test } from "node:test";
import { movedPages } from "../lib/pageOrder";

test("only the actively moved page is highlighted, not displaced pages", () => {
  assert.deepEqual([...movedPages(["a", "b", "c", "d"], ["b", "c", "d", "a"], new Set(["a"]))], ["a"]);
});

test("returning to the default order clears the highlight", () => {
  assert.equal(movedPages(["a", "b", "c"], ["a", "b", "c"], new Set(["a"])).size, 0);
});

test("a matching numeric index does not hide a page still in the wrong relative order", () => {
  assert.deepEqual([...movedPages(["a", "b", "c"], ["c", "b", "a"], new Set(["b", "c"]))], ["c", "b"]);
});

test("several explicitly moved pages stay marked until individually restored", () => {
  const baseline = ["a", "b", "c", "d"];
  assert.deepEqual([...movedPages(baseline, ["c", "d", "a", "b"], new Set(["a", "b"]))], ["a", "b"]);
  assert.deepEqual([...movedPages(baseline, ["a", "c", "d", "b"], new Set(["a", "b"]))], ["b"]);
});

test("a previously restored page stays unmarked when another page moves past it", () => {
  const baseline = ["a", "b", "c"];
  const restored = movedPages(baseline, baseline, new Set(["a"]));
  assert.deepEqual([...movedPages(baseline, ["c", "a", "b"], new Set([...restored, "c"]))], ["c"]);
});

test("removal and added PDFs do not create spurious highlights", () => {
  assert.equal(movedPages(["a", "c"], ["a", "c"], new Set(["b", "c"])).size, 0);
  assert.deepEqual([...movedPages(["a", "b", "c", "new"], ["b", "c", "a", "new"], new Set(["a"]))], ["a"]);
});

test("duplicate source pages use distinct occurrence IDs", () => {
  assert.deepEqual([...movedPages(["a:1", "a:2", "b"], ["a:2", "b", "a:1"], new Set(["a:1"]))], ["a:1"]);
});

test("reset clears the marker set", () => {
  assert.equal(movedPages(["a", "b"], ["b", "a"], new Set()).size, 0);
});
