"""惊喜附言封存揭晓:勾选 seal_note 后附言落库但对外遮蔽,核销时揭晓。

分三件:
- policy.py      封存策略(何时可见、何时可改)——全部拍板口径的唯一出处
- projection.py  可见性投影(墙卡/公开详情/我的认领/已完成共用,三路同钉)
- reveal.py      揭晓写库(核销事务内把揭晓时刻落库)
"""
from app.modules.seal_note.policy import is_revealed, note_edit_allowed, note_visible
from app.modules.seal_note.projection import project_rows, project_wish
from app.modules.seal_note.reveal import apply_reveal, reveal_needed

__all__ = [
    "is_revealed",
    "note_edit_allowed",
    "note_visible",
    "project_rows",
    "project_wish",
    "apply_reveal",
    "reveal_needed",
]
