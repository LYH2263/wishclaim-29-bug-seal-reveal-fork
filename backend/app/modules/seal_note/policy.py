"""封存策略:可见性与改写口径的唯一出处(纯函数,不落库)。

拍板口径:
1. 认领人核销前同样不可读封存附言——任何人、任何读路径,核销前一律遮蔽。
2. 已认领未核销(claimed)的封存附言冻结:禁止改写(含解封);
   open/released 可改;fulfilled 后附言成为最终历史,一律不可改。
3. 揭晓只随核销成功发生:fulfilled 是揭晓的兜底真源,
   核销失败事务整体回滚,不存在「闪过明文又收回」的中间态。
"""

REVEAL_STATUS = "fulfilled"
EDITABLE_STATUS = ("open", "released")


def is_revealed(seal_note: bool, status: str, note_revealed_at: str | None) -> bool:
    """封存附言是否已揭晓。未勾选 seal_note 无所谓揭晓(投影直接放行)。

    status=='fulfilled' 是兜底真源:即使揭晓写库漏写,已核销愿望也不会卡在封存态,
    结构上杜绝「已完成放全文而墙卡仍封」这类分叉。
    """
    if not seal_note:
        return False
    if status == REVEAL_STATUS:
        return True
    return bool(note_revealed_at)


def note_visible(seal_note: bool, status: str, note_revealed_at: str | None) -> bool:
    """附言明文是否可读:未封存恒可见(与改造前一致);封存后仅揭晓可见。"""
    if not seal_note:
        return True
    return is_revealed(seal_note, status, note_revealed_at)


def note_edit_allowed(seal_note: bool, status: str) -> dict:
    """发布者改写附言/封存标记的口径。返回 {"ok": bool, "reason": str}。

    fulfilled 一律不可改;封存行在 claimed 期间冻结(禁止改正文、禁止解封);
    未封存行的既有改写口径不动(open/claimed/released 均可,fulfilled 不可)。
    """
    if status == REVEAL_STATUS:
        return {"ok": False, "reason": "fulfilled_immutable"}
    if seal_note and status not in EDITABLE_STATUS:
        return {"ok": False, "reason": "claimed_note_frozen"}
    return {"ok": True, "reason": ""}
