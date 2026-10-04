"""揭晓写库:核销事务内把封存附言的揭晓时刻落库(幂等,首揭时间不被覆盖)。"""
from datetime import datetime


def reveal_needed(seal_note: bool, note_revealed_at: str | None) -> bool:
    """封存且尚未揭晓才需要写库;未封存或已揭晓都是 no-op。"""
    return bool(seal_note) and not note_revealed_at


def apply_reveal(conn, wish, now: datetime) -> bool:
    """在 fulfill 同一事务内调用。wish 为核销前的行(需含 id/seal_note/note_revealed_at)。

    返回是否真正写库。WHERE note_revealed_at IS NULL 兜底并发重复核销。
    """
    if not reveal_needed(bool(wish["seal_note"]), wish["note_revealed_at"]):
        return False
    conn.execute(
        "UPDATE wishes SET note_revealed_at=? WHERE id=? AND note_revealed_at IS NULL",
        (now.isoformat(), wish["id"]),
    )
    return True
