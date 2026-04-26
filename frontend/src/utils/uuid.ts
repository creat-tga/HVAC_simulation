/**
 * 生成 UUID v4 字符串。
 *
 * 浏览器 `crypto.randomUUID()` 仅在 secure context（https / localhost）
 * 才可用：通过 http + 内网 IP（如 192.168.x.x:5173）访问时，移动端
 * Chrome / Safari 会抛 `TypeError: crypto.randomUUID is not a function`。
 *
 * 该工具函数按优先级回退：
 *   1. `crypto.randomUUID()` —— 标准 API
 *   2. `crypto.getRandomValues()` —— 几乎所有现代浏览器（含 http 环境）都支持
 *   3. `Math.random()` —— 最后兜底（弱随机，仅作为 UI key 使用）
 */
export function randomUUID(): string {
  try {
    const c = (typeof globalThis !== 'undefined' ? (globalThis as unknown as { crypto?: Crypto }).crypto : undefined)
    if (c && typeof c.randomUUID === 'function') {
      return c.randomUUID()
    }
    if (c && typeof c.getRandomValues === 'function') {
      const bytes = new Uint8Array(16)
      c.getRandomValues(bytes)
      bytes[6] = (bytes[6] & 0x0f) | 0x40
      bytes[8] = (bytes[8] & 0x3f) | 0x80
      const hex: string[] = []
      for (let i = 0; i < 16; i += 1) {
        hex.push(bytes[i].toString(16).padStart(2, '0'))
      }
      return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`
    }
  } catch {
    // fallthrough
  }
  const tpl = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
  return tpl.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    const v = ch === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
