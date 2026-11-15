// Display formatting of package and card values: rounding and units only, no science.

/** Seconds to whole hours, for display. */
export const wholeHours = (seconds: number): number => Math.round(seconds / 3600);

/** A share (0..1) as a percentage, "31 %". */
export const percent = (share: number, digits = 0): string => `${(share * 100).toFixed(digits)} %`;

const COMPARISON: Record<string, string> = { ">=": "≥", "<=": "≤", ">": ">", "<": "<" };

/** A comparison operator of the card ("<", ">=") as a symbol. */
export const comparisonSymbol = (op: string): string => COMPARISON[op] ?? op;

/** A measured value or threshold of the card with its unit; shares are shown as percentages. */
export function cardValue(v: { value: number; unit: string }, digits = 1): string {
  return v.unit === "share of points" ? percent(v.value, digits) : `${v.value} ${v.unit}`;
}

/** A site name without its parenthesised detail: "Apollo 11 (Lunar Module …)" → "Apollo 11". */
export const shortName = (name: string): string => name.replace(/\s*\(.*\)\s*$/, "");
