from app.db import connect

def init_db():
    c = connect()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS wishes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, note TEXT, status TEXT,
      claimer TEXT, claimed_at TEXT, expires_at TEXT, data_quality TEXT,
      seal_note INTEGER NOT NULL DEFAULT 0, note_revealed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    _migrate(c)
    if c.execute("SELECT COUNT(*) c FROM wishes").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO wishes(title,note,status,claimer,claimed_at,expires_at,data_quality,seal_note,note_revealed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("机械键盘", "红轴", "open", None, None, None, "clean", 0, None),
                ("围巾", "羊毛", "open", None, None, None, "clean", 0, None),
                ("惊喜盒子", "附言里藏着给你的小礼物线索", "open", None, None, None, "clean", 1, None),
                ("脏愿望-空标题", "", "open", None, None, None, "dirty", 0, None),
                ("过期锁样例", "应被TTL释放", "claimed", "ghost", "2020-01-01T00:00:00+00:00",
                 "2020-01-01T01:00:00+00:00", "dirty", 0, None),
            ],
        )
        c.execute("INSERT INTO settings(key,value) VALUES ('ttl_seconds','86400')")
        c.execute("INSERT INTO settings(key,value) VALUES ('wall_title','暖粉愿望墙')")
        c.commit()
    c.close()

def _migrate(c):
    """老库补列:seal_note 默认 0(未封存,行为与改造前一致)。"""
    cols = {r["name"] for r in c.execute("PRAGMA table_info(wishes)")}
    if "seal_note" not in cols:
        c.execute("ALTER TABLE wishes ADD COLUMN seal_note INTEGER NOT NULL DEFAULT 0")
    if "note_revealed_at" not in cols:
        c.execute("ALTER TABLE wishes ADD COLUMN note_revealed_at TEXT")
    c.commit()
