// Formatters — all money is INR (never a dollar sign anywhere in this app or repo).

export function inr(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value);
}

export function num(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}

export function dec(value: number, digits = 2): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function pct(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`;
}
