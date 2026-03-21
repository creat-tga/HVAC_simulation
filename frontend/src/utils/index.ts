/**
 * Format a date string to localized display.
 */
export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

/**
 * Format a number with fixed decimal places.
 */
export function formatNumber(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '-'
  return value.toFixed(decimals)
}
