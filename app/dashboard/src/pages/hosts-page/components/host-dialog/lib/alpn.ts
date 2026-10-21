export const alpnOptions = ["h3", "h2", "http/1.1"] as const;

export function getAlpnSelection(text: string): string[] {
  if (!text) return [];
  try {
    const values: unknown = JSON.parse(text);
    if (
      Array.isArray(values) &&
      values.every((value) => typeof value === "string")
    ) {
      return [...new Set(values)];
    }
  } catch {
    // Keep malformed stored input untouched until the user changes the selection.
  }
  return [];
}
