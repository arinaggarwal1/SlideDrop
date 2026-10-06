/**
 * Only explicitly moved pages can be marked. A page is back in place when its
 * order relative to every remaining page matches the default order, even if
 * its numeric position changed because pages were added or removed.
 * Prefix/suffix ranks detect those crossings in linear time.
 */
export function movedPages(
  defaultIds: readonly string[],
  orderedIds: readonly string[],
  explicitlyMoved: ReadonlySet<string>,
): Set<string> {
  const rank = new Map(defaultIds.map((id, index) => [id, index]));
  const present = orderedIds.filter(id => rank.has(id));
  const suffixMin = new Array<number>(present.length + 1).fill(Infinity);
  for (let index = present.length - 1; index >= 0; index--) {
    suffixMin[index] = Math.min(rank.get(present[index])!, suffixMin[index + 1]);
  }
  const moved = new Set<string>();
  let prefixMax = -1;
  present.forEach((id, index) => {
    const original = rank.get(id)!;
    if (explicitlyMoved.has(id) && (prefixMax > original || suffixMin[index + 1] < original)) {
      moved.add(id);
    }
    prefixMax = Math.max(prefixMax, original);
  });
  return moved;
}
