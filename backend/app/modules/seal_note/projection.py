"""可见性投影:墙卡 / 公开详情 / 我的认领 / 已完成共用同一投影函数。

所有读路径只许经这里出仓,因此「墙已揭晓而详情仍封」在结构上不可能出现;
未勾选 seal_note 的愿望逐字节透传,展示与改造前一致。
"""
from app.modules.seal_note.policy import is_revealed, note_visible


def project_wish(row: dict) -> dict:
    w = dict(row)
    sealed = bool(w.get("seal_note"))
    status = w.get("status")
    revealed_at = w.get("note_revealed_at")
    w["seal_note"] = sealed
    w["note_revealed"] = is_revealed(sealed, status, revealed_at)
    if status == "fulfilled":
        w["note_revealed"] = True
    if not note_visible(sealed, status, revealed_at) and status != "fulfilled":
        w["note"] = ""
    return w


def project_rows(rows) -> list:
    return [project_wish(r) for r in rows]
