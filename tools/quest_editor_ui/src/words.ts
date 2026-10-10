// Russian numerals: 1 ошибка, 2 ошибки, 5 ошибок, 11 ошибок, 21 ошибка.
export function plural(n: number, one: string, few: string, many: string): string {
  const d = Math.abs(n) % 100;
  const u = d % 10;
  if (d >= 11 && d <= 14) return many;
  if (u === 1) return one;
  if (u >= 2 && u <= 4) return few;
  return many;
}

export const count = (n: number, one: string, few: string, many: string) => `${n} ${plural(n, one, few, many)}`;
