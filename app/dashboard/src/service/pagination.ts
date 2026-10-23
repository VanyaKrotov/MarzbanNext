type Page<T> = { items: T[]; total: number };

export async function fetchAllPages<T>(
  fetchPage: (offset: number) => Promise<Page<T>>,
): Promise<T[]> {
  const items: T[] = [];
  let total = 1;
  while (items.length < total) {
    const page = await fetchPage(items.length);
    if (page.items.length === 0) break;
    items.push(...page.items);
    total = page.total;
  }
  return items;
}
