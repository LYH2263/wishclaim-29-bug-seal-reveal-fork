import pytest

# DATA_DIR 由每个用例的 fixture 在启动 TestClient 前指到临时目录,
# 导入 app 本身不触库。
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """每个用例一个全新 sqlite 库,seed 样例行不干扰按 id 的断言。"""
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(db_dir))
    # 进入 context 触发 startup -> seed.init_db(),此刻 DATA_DIR 已指向临时库。
    with TestClient(app) as c:
        yield c
