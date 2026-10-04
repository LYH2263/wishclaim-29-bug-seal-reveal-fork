from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.modules.seal_note.policy import note_edit_allowed
from app.modules.seal_note.projection import project_rows, project_wish
from app.modules.seal_note.reveal import apply_reveal

app = FastAPI(title="Wishclaim", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

def now(): return datetime.now(timezone.utc)

def ttl():
    c = connect(); row = c.execute("SELECT value FROM settings WHERE key='ttl_seconds'").fetchone(); c.close()
    return int(row["value"] if row else 86400)

def sweep(c):
    for r in c.execute("SELECT * FROM wishes WHERE status='claimed'"):
        rel = release_if_expired(r["status"], r["expires_at"], now())
        if rel:
            c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=? WHERE id=?",
                      (rel["status"], None, None, None, r["id"]))

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = [dict(r) for r in c.execute("SELECT * FROM wishes ORDER BY id DESC")]; c.close()
    # 墙卡与公开详情/我的认领/已完成走同一投影:核销成功的封存行在此同样放全文,
    # 禁止任何读路径二次遮蔽。
    return project_rows(rows)

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    if not r: raise HTTPException(404, "not found")
    return project_wish(dict(r))

class WishIn(BaseModel):
    title: str
    note: str = ""
    seal_note: bool = False

@app.post("/api/wishes")
def create_wish(body: WishIn):
    c = connect()
    cur = c.execute("INSERT INTO wishes(title,note,status,data_quality,seal_note) VALUES (?,?,?,?,?)",
                    (body.title, body.note, "open", "clean", int(body.seal_note)))
    c.commit(); wid = cur.lastrowid; c.close(); return {"id": wid}

class NoteEditIn(BaseModel):
    note: str | None = None
    seal_note: bool | None = None

@app.patch("/api/wishes/{wid}/note")
def edit_note(wid: int, body: NoteEditIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = note_edit_allowed(bool(r["seal_note"]), r["status"])
    if not allowed["ok"]:
        c.close(); raise HTTPException(409, allowed["reason"])
    note = r["note"] if body.note is None else body.note
    seal = r["seal_note"] if body.seal_note is None else int(body.seal_note)
    # 能走到这里必未核销,揭晓戳必须为空:改写封存/解封切换都不允许携带旧揭晓标记,
    # 杜绝「半份新正文 + 半份旧封条」的版本漂移。
    c.execute(
        "UPDATE wishes SET note=?, seal_note=?, note_revealed_at=NULL WHERE id=?",
        (note, seal, wid),
    )
    c.commit(); c.close()
    return {"ok": True, "seal_note": bool(seal)}

class ClaimIn(BaseModel):
    claimer: str

@app.post("/api/wishes/{wid}/claim")
def claim(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = claim_allowed(r["status"], r["claimer"], now(), r["expires_at"])
    if not allowed["ok"]:
        c.close(); raise HTTPException(409, allowed["reason"])
    p = lock_payload(body.claimer, now(), ttl())
    c.execute("UPDATE wishes SET status=?, claimer=?, claimed_at=?, expires_at=? WHERE id=?",
              (p["status"], p["claimer"], p["claimed_at"], p["expires_at"], wid))
    c.commit(); c.close(); return p

@app.post("/api/wishes/{wid}/release")
def release(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    c.execute("UPDATE wishes SET status='released', claimer=NULL, claimed_at=NULL, expires_at=NULL WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "released"}

@app.post("/api/wishes/{wid}/fulfill")
def fulfill(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "need_claim")
    # 状态翻转与揭晓落库同一事务:任一步失败整体回滚,封存行保持封条,
    # 不存在「详情已闪过明文、核销失败后收不回」的中间态。
    try:
        c.execute("UPDATE wishes SET status='fulfilled' WHERE id=?", (wid,))
        apply_reveal(c, r, now())
        c.commit()
    except Exception:
        c.rollback(); c.close(); raise
    c.close(); return {"ok": True, "status": "fulfilled"}

@app.get("/api/mine")
def mine(claimer: str):
    c = connect(); sweep(c); c.commit()
    rows = [dict(r) for r in c.execute("SELECT * FROM wishes WHERE claimer=?", (claimer,))]; c.close()
    return project_rows(rows)

@app.get("/api/done")
def done():
    c = connect()
    rows = [dict(r) for r in c.execute("SELECT * FROM wishes WHERE status='fulfilled'")]; c.close()
    return project_rows(rows)

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.get("/api/rules")
def rules():
    return {
        "mutex": "同一愿望同时只能被一人认领",
        "ttl": "认领超时未核销则自动释放",
        "fulfill": "核销后状态变为 fulfilled",
        "seal_note": "惊喜附言封存:勾选后墙卡/公开详情/我的认领一律遮蔽明文,认领人核销前同样不可读",
        "seal_reveal": "核销时揭晓落库,已完成页与详情同步展示附言全文",
        "seal_edit": "封存附言在已认领未核销期间禁止改写;未认领(open/released)可改,已核销不可再改",
    }
