"""惊喜附言封存揭晓的口径测试:策略/投影纯函数 + 四条读路径同钉。

拍板口径(详见 policy.py docstring):
- 任何人、任何读路径,核销前一律遮蔽;认领人无特权。
- 揭晓只发生在核销成功落库时;核销失败/过期释放保持封存,不存在先揭后收。
- 已认领未核销的封存附言禁止改写(含解封);open/released 可改,fulfilled 不可改。
- 未勾选 seal_note 的旧行逐字节透传,任何状态都不挡。
"""
import pytest

from app.modules.seal_note.policy import is_revealed, note_edit_allowed, note_visible
from app.modules.seal_note.projection import project_wish


# ---------- 策略纯函数 ----------

class TestPolicy:
    @pytest.mark.parametrize("status", ["open", "released", "claimed", "fulfilled"])
    def test_unsealed_always_visible(self, status):
        assert note_visible(False, status, None) is True
        assert is_revealed(False, status, None) is False

    @pytest.mark.parametrize("status", ["open", "released", "claimed"])
    def test_sealed_hidden_before_reveal(self, status):
        assert note_visible(True, status, None) is False
        assert is_revealed(True, status, None) is False

    def test_sealed_visible_after_reveal_written(self):
        assert note_visible(True, "fulfilled", "2026-10-04T00:00:00+00:00") is True

    def test_fulfilled_is_fallback_truth(self):
        # 揭晓写库漏写/老数据没有 note_revealed_at:已核销也必须视为已揭晓,
        # 结构上杜绝「详情已揭而已完成仍封」
        assert is_revealed(True, "fulfilled", None) is True
        assert note_visible(True, "fulfilled", None) is True

    def test_edit_rules(self):
        assert note_edit_allowed(True, "open")["ok"]
        assert note_edit_allowed(True, "released")["ok"]
        assert not note_edit_allowed(True, "claimed")["ok"]    # 已认领未核销:禁改含解封
        assert not note_edit_allowed(True, "fulfilled")["ok"]
        assert note_edit_allowed(False, "claimed")["ok"]       # 未封存行不受封存口径约束
        assert not note_edit_allowed(False, "fulfilled")["ok"]


# ---------- 投影 ----------

def row(**kw):
    base = dict(id=1, title="t", note="正文", status="open", claimer=None,
                claimed_at=None, expires_at=None, data_quality="clean",
                seal_note=0, note_revealed_at=None)
    base.update(kw)
    return base


class TestProjection:
    def test_unsealed_passthrough_byte_for_byte(self):
        w = project_wish(row(note="原文不动 👀", status="fulfilled"))
        assert w["note"] == "原文不动 👀"
        assert w["note_revealed"] is False

    def test_sealed_masked_before_reveal(self):
        w = project_wish(row(seal_note=1, status="claimed"))
        assert w["note"] == ""
        assert w["note_revealed"] is False

    def test_sealed_revealed_after_fulfill(self):
        w = project_wish(row(seal_note=1, status="fulfilled",
                             note_revealed_at="2026-10-04T00:00:00+00:00"))
        assert w["note"] == "正文"
        assert w["note_revealed"] is True

    def test_sealed_fulfilled_without_timestamp_still_revealed(self):
        w = project_wish(row(seal_note=1, status="fulfilled"))
        assert w["note"] == "正文"
        assert w["note_revealed"] is True


# ---------- 端点:墙卡/公开详情/我的认领/已完成四处同钉 ----------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def create_sealed(client, note="藏着的话"):
    r = client.post("/api/wishes", json={"title": "惊喜", "note": note, "seal_note": True})
    assert r.status_code == 200
    return r.json()["id"]


def all_read_paths(client, wid, claimer="小甲"):
    """同一条愿望在墙卡/公开详情/我的认领/已完成四处的投影(未出现处为 None)。"""
    wall = next(w for w in client.get("/api/wishes").json() if w["id"] == wid)
    detail = client.get(f"/api/wishes/{wid}").json()
    mine = next((w for w in client.get("/api/mine", params={"claimer": claimer}).json()
                 if w["id"] == wid), None)
    done = next((w for w in client.get("/api/done").json() if w["id"] == wid), None)
    return wall, detail, mine, done


class TestSealedLifecycle:
    def test_masked_everywhere_before_fulfill(self, client):
        wid = create_sealed(client)
        client.post(f"/api/wishes/{wid}/claim", json={"claimer": "小甲"})
        wall, detail, mine, _ = all_read_paths(client, wid)
        for w in (wall, detail, mine):
            assert w["note"] == ""             # 认领人核销前同样不可读
            assert w["note_revealed"] is False

    def test_revealed_everywhere_after_fulfill(self, client):
        wid = create_sealed(client)
        client.post(f"/api/wishes/{wid}/claim", json={"claimer": "小甲"})
        client.post(f"/api/wishes/{wid}/fulfill")
        wall, detail, mine, done = all_read_paths(client, wid)
        assert done is not None
        for w in (wall, detail, mine, done):   # 四处同揭,禁止「已完成全文、墙仍封」
            assert w["note"] == "藏着的话"
            assert w["note_revealed"] is True
        assert detail["note_revealed_at"]

    def test_failed_fulfill_keeps_seal(self, client):
        wid = create_sealed(client)
        r = client.post(f"/api/wishes/{wid}/fulfill")   # 未认领直接核销 → 400
        assert r.status_code == 400
        wall, detail, _, _ = all_read_paths(client, wid)
        for w in (wall, detail):
            assert w["note"] == ""             # 失败不揭晓,无需收回
            assert w["note_revealed"] is False
            assert w["note_revealed_at"] is None

    def test_edit_blocked_while_claimed_sealed(self, client):
        wid = create_sealed(client)
        client.post(f"/api/wishes/{wid}/claim", json={"claimer": "小甲"})
        r = client.patch(f"/api/wishes/{wid}/note", json={"note": "换新句", "seal_note": True})
        assert r.status_code == 409
        r = client.patch(f"/api/wishes/{wid}/note", json={"seal_note": False})  # 解封也禁
        assert r.status_code == 409
        client.post(f"/api/wishes/{wid}/fulfill")
        assert client.get(f"/api/wishes/{wid}").json()["note"] == "藏着的话"  # 揭的仍是原句

    def test_edit_while_open_reveals_new_sentence(self, client):
        wid = create_sealed(client, note="旧句")
        r = client.patch(f"/api/wishes/{wid}/note", json={"note": "新句", "seal_note": True})
        assert r.status_code == 200
        wall, detail, _, _ = all_read_paths(client, wid)
        assert wall["note"] == detail["note"] == ""  # 占位吃新句:仍遮蔽,两处同版本
        client.post(f"/api/wishes/{wid}/claim", json={"claimer": "小甲"})
        client.post(f"/api/wishes/{wid}/fulfill")
        wall, detail, mine, done = all_read_paths(client, wid)
        for w in (wall, detail, mine, done):
            assert w["note"] == "新句"         # 揭晓揭的是最终保存版

    def test_edit_blocked_after_fulfill(self, client):
        wid = create_sealed(client)
        client.post(f"/api/wishes/{wid}/claim", json={"claimer": "小甲"})
        client.post(f"/api/wishes/{wid}/fulfill")
        r = client.patch(f"/api/wishes/{wid}/note", json={"note": "改写", "seal_note": True})
        assert r.status_code == 409


class TestUnsealedLegacyRows:
    def test_unsealed_never_masked(self, client):
        wid = client.post("/api/wishes", json={"title": "普通", "note": "明码"}).json()["id"]
        client.post(f"/api/wishes/{wid}/claim", json={"claimer": "小甲"})
        before = all_read_paths(client, wid)
        client.post(f"/api/wishes/{wid}/fulfill")
        after = all_read_paths(client, wid)
        for group in (before, after):
            for w in group:
                if w is None:
                    continue
                assert w["note"] == "明码"     # 旧行不得被改成先挡后开
                assert w["note_revealed"] is False
