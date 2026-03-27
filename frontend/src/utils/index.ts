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

/**
 * Calculate character length where CJK chars count as 1, ASCII chars count as 0.5.
 * Returns the "Chinese character equivalent" length.
 */
export function getCharLength(str: string): number {
  let len = 0
  for (const ch of str) {
    // CJK Unified Ideographs and common fullwidth ranges
    if (ch.charCodeAt(0) > 127) {
      len += 1
    } else {
      len += 0.5
    }
  }
  return len
}

/**
 * Create a name length validator: max 15 Chinese characters (30 ASCII).
 * Accepts an i18n t function for localized error messages.
 */
export function createNameValidator(t: (key: string) => string) {
  return (_rule: unknown, value: string, callback: (err?: Error) => void) => {
    if (value && getCharLength(value) > 15) {
      callback(new Error(t('common.nameCharLimit')))
    } else {
      callback()
    }
  }
}
