# Wishclaim · 礼物愿望认领

发布 → 认领锁定（互斥+TTL）→ 核销/释放。可勾选 `seal_note` 封存惊喜附言：核销前墙卡/详情/我的认领一律遮蔽（认领人无特权），核销时揭晓落库，已完成页与详情同揭全文；封存附言已认领未核销禁止改写。

| 服务 | 端口 |
| --- | --- |
| 前端 | 5200 |
| API | 10200 |

```bash
docker compose up --build
pytest backend/app/tests
```

0-1：`wish_comment` / `secret_santa` / `price_cap`。
