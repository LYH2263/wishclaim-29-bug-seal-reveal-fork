// 封存附言的前端口径:与后端 projection 同钉——
// 未勾选 seal_note 时原样展示;封存未揭晓时一律占位,揭晓后展示全文。
// 后端在未揭晓时根本不下发明文(note 为空串),前端不再按 status 自行猜测,
// 墙卡/公开详情/我的认领/已完成四处共用这一个函数。
export const SEAL_PLACEHOLDER = '🔒 惊喜附言已封存 · 核销后揭晓'

export function noteMasked(w) {
  return !!(w.seal_note && !w.note_revealed)
}

export function noteText(w) {
  return noteMasked(w) ? SEAL_PLACEHOLDER : (w.note || '')
}
