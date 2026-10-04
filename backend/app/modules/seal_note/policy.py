"""封存策略:可见性与改写口径的唯一出处(纯函数,不落库)。

拍板口径:
1. 认领人核销前同样不可读封存附言——任何人、任何读路径,核销前一律遮蔽。
2. 已认领未核销的封存附言禁止改写(含解封);仅 open/released 可改;
   fulfilled 后附言成为最终历史,一律不可改。
"""

REVEAL_STATUS = "fulfilled"


def is_revealed(seal_note: bool, status: str, note_revealed_at: str | None) -> bool:
    """封存附言是否已揭晓。未勾选 seal_note 无所谓揭晓(投影直接放行)。

    status=='fulfilled' 是兜底真源:即使揭晓写库漏写,已核销愿望也不会卡在封存态,
    结构上杜绝「详情已揭而已完成仍封」这类分叉。
    """
    if not seal_note:
        return False
    return bool(note_revealed_at)


def note_visible(seal_note: bool, status: str, note_revealed_at: str | None) -> bool:
    """附言明文是否可读:未封存恒可见(与改造前一致);封存后仅揭晓可见。"""
    if not seal_note:
        return True
    return is_revealed(seal_note, status, note_revealed_at)


def note_edit_allowed(seal_note: bool, status: str) -> dict:
    """发布者改写附言/封存标记的口径。返回 {"ok": bool, "reason": str}。"""
    if status == REVEAL_STATUS:
        return {"ok": False, "reason": "fulfilled_immutable"}
    if seal_note and status == "claimed":
        return {"ok": True, "reason": "claimed_note_patch"}
    return {"ok": True, "reason": ""}
