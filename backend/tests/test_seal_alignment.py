import os
import pytest

# 必须在导入 app 之前指好临时库,启动事件据此建表。
_TMP_DATA = os.path.join(os.path.dirname(__file__), "_tmp_data")
os.environ["DATA_DIR"] = _TMP_DATA

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """每个用例一个全新 sqlite 库,避免 seed 样例干扰断言。"""
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(db_dir))
    # startup 已在导入时跑过;这里直接对新库建表。
    from app import seed
    seed.init_db()
    with TestClient(app) as c:
        yield c


SECRET = "附言里藏着给你的小礼物线索"


def _make(client, title, note=SECRET, seal=True):
    r = client.post("/api/wishes", json={"title": title, "note": note, "seal_note": seal})
    assert r.status_code == 200
    return r.json()["id"]


def _views(client, wid, claimer="访客"):
    """四条读路径对同一愿望的快照。"""
    wall = next(w for w in client.get("/api/wishes").json() if w["id"] == wid)
    detail = client.get(f"/api/wishes/{wid}").json()
    mine = next((w for w in client.get(f"/api/mine?claimer={claimer}").json() if w["id"] == wid), None)
    done = next((w for w in client.get("/api/done").json() if w["id"] == wid), None)
    return wall, detail, mine, done


def _assert_masked(w):
    assert w["seal_note"] is True
    assert w["note_revealed"] is False
    assert w["note"] == "", "封存未揭晓不得下发任何明文"


def _assert_revealed(w):
    assert w["seal_note"] is True
    assert w["note_revealed"] is True
    assert w["note"] == SECRET, "核销成功后应下发附言全文"


def test_sealed_hidden_everywhere_before_fulfill(client):
    """拍板口径:核销前任何人、任何读路径都不可读封存明文,认领人也不行。"""
    wid = _make(client, "惊喜盒子")
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})

    wall, detail, mine, done = _views(client, wid)
    _assert_masked(wall)
    _assert_masked(detail)
    assert mine is not None and mine["status"] == "claimed"
    _assert_masked(mine)  # 「我的认领」与路人公开详情同一口径
    assert done is None  # 未核销不出现在已完成页


def test_fulfill_success_reveals_everywhere_atomically(client):
    """核销成功:已完成页、公开详情、墙卡三处同时揭晓全文,禁止墙仍封。"""
    wid = _make(client, "惊喜盒子")
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})
    r = client.post(f"/api/wishes/{wid}/fulfill")
    assert r.status_code == 200

    wall, detail, mine, done = _views(client, wid)
    _assert_revealed(wall)
    _assert_revealed(detail)
    assert mine is not None
    _assert_revealed(mine)
    assert done is not None and done["note_revealed_at"]
    _assert_revealed(done)


def test_fulfill_failure_keeps_seal_everywhere(client):
    """核销失败:不存在的核销前提被拒后,封条原样保留,任何路径都不得闪过明文。"""
    wid = _make(client, "惊喜盒子")
    # open 状态直接核销 -> 400
    r = client.post(f"/api/wishes/{wid}/fulfill")
    assert r.status_code == 400

    wall, detail, mine, done = _views(client, wid)
    _assert_masked(wall)
    _assert_masked(detail)
    assert mine is None
    assert done is None


def test_sealed_note_frozen_while_claimed(client):
    """拍板口径:已认领未核销的封存附言冻结,改正文/解封一律 409。"""
    wid = _make(client, "惊喜盒子")
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})

    r = client.patch(f"/api/wishes/{wid}/note", json={"note": "新句不该进来"})
    assert r.status_code == 409 and r.json()["detail"] == "claimed_note_frozen"
    r = client.patch(f"/api/wishes/{wid}/note", json={"seal_note": False})
    assert r.status_code == 409

    wall, detail, _, _ = _views(client, wid)
    _assert_masked(wall)
    _assert_masked(detail)  # 墙卡与公开详情同一版本,无新旧句漂移


def test_sealed_note_editable_when_open_placeholder_never_leaks(client):
    """拍板口径:未认领(open)可改;新句在核销前仍只显示封条,占位不吃新句。"""
    wid = _make(client, "惊喜盒子")
    r = client.patch(f"/api/wishes/{wid}/note", json={"note": "发布者改的新句"})
    assert r.status_code == 200

    wall, detail, _, _ = _views(client, wid)
    _assert_masked(wall)
    _assert_masked(detail)
    assert "新句" not in wall["note"] and "新句" not in detail["note"]

    # 核销成功后揭晓的是新句,不是旧封条里的旧句
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})
    client.post(f"/api/wishes/{wid}/fulfill")
    wall, detail, _, done = _views(client, wid)
    assert wall["note"] == "发布者改的新句"
    assert detail["note"] == "发布者改的新句"
    assert done["note"] == "发布者改的新句"


def test_released_sealed_row_editable_then_reveals(client):
    """released(认领超时/主动释放)同 open:可改,核销前仍封。"""
    wid = _make(client, "惊喜盒子")
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})
    client.post(f"/api/wishes/{wid}/release")
    assert client.patch(f"/api/wishes/{wid}/note", json={"note": "释放后改的句"}).status_code == 200
    _, detail, _, done = _views(client, wid)
    _assert_masked(detail)
    assert done is None


def test_fulfilled_note_immutable(client):
    wid = _make(client, "惊喜盒子")
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})
    client.post(f"/api/wishes/{wid}/fulfill")
    r = client.patch(f"/api/wishes/{wid}/note", json={"note": "核销后想改"})
    assert r.status_code == 409 and r.json()["detail"] == "fulfilled_immutable"


def test_unsealed_legacy_row_always_plaintext(client):
    """回归:未勾选封存的旧行全程明文,绝不被这次对齐改成先挡后开。"""
    plain = "红轴手感"
    wid = _make(client, "机械键盘", note=plain, seal=False)

    wall, detail, mine, done = _views(client, wid)
    assert wall["note"] == plain and wall["note_revealed"] is False
    assert detail["note"] == plain
    assert mine is None and done is None

    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})
    client.post(f"/api/wishes/{wid}/fulfill")
    wall, detail, mine, done = _views(client, wid)
    for w in (wall, detail, mine, done):
        assert w["note"] == plain
        assert w["note_revealed"] is False  # 未封存无所谓揭晓标记


def test_seal_toggle_consistency(client):
    """先封存后解封:解封即可读;重新封存后四路立刻重新遮蔽,不留旧揭晓戳。"""
    wid = _make(client, "惊喜盒子", note=SECRET)
    # open 期允许解封切换
    assert client.patch(f"/api/wishes/{wid}/note", json={"seal_note": False}).status_code == 200
    _, detail, _, _ = _views(client, wid)
    assert detail["note"] == SECRET and detail["note_revealed"] is False

    assert client.patch(f"/api/wishes/{wid}/note", json={"seal_note": True}).status_code == 200
    wall, detail, _, _ = _views(client, wid)
    _assert_masked(wall)
    _assert_masked(detail)


def test_edit_and_fulfill_overlap_no_half_state(client):
    """核销与改附言叠在一起:claimed 期间 PATCH 被拒,核销后只能揭晓旧句,
    数据库里不存在「半份新正文 + 半份旧封条」。"""
    wid = _make(client, "惊喜盒子")
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})
    # 核销请求失败(模拟并发前提不满足的一种:重复核销前先造一次失败)
    client.post(f"/api/wishes/{wid}/release")
    client.post(f"/api/wishes/{wid}/claim", json={"claimer": "访客"})
    # claimed 改附言被拒
    pr = client.patch(f"/api/wishes/{wid}/note", json={"note": "半新半旧?"})
    assert pr.status_code == 409
    # 核销照常成功,揭晓的是冻结的旧句
    assert client.post(f"/api/wishes/{wid}/fulfill").status_code == 200
    *_, done = _views(client, wid)
    assert done["note"] == SECRET and done["note_revealed"] is True
