// 封存附言的前端口径:与后端 projection 同钉——
// 未勾选 seal_note 时原样展示;封存未揭晓时一律占位,揭晓后展示全文。
// 核销失败不揭晓:前端不乐观揭明文,只渲染服务端投影,失败无需收回。
export const SEAL_PLACEHOLDER = '🔒 惊喜附言已封存 · 核销后揭晓'

export function noteMasked(w) {
  return !!(w.seal_note && !w.note_revealed)
}

export function noteText(w) {
  return noteMasked(w) ? SEAL_PLACEHOLDER : (w.note || '')
}
