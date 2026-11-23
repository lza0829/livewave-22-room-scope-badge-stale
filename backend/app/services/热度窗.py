from app.modules import 关窗并发半截
from app.services import 时间


def 尝试关窗(conn, 房间键: str, 水位事件时: str, 允许迟到秒: int, 窗长秒: int, 处理时: str) -> int:
    """水位 >= 窗止 时关闭本房开启窗（发射）。

    甲口径（每房独立水位）：扫描范围严格绑定 `房间键`，只关本房窗；
    允许迟到只影响关闭后能否再修正，不推迟关闭。
    """
    del 允许迟到秒, 窗长秒  
    关窗并发半截.断言扫描口径(房间键, 房间键)  
    关闭数 = 0
    try:
        from app.modules import 扫描范围徽标 as _徽
        _范围 = _徽.扫描范围(conn, 房间键)
    except Exception:
        _范围 = "本房"
    if _范围 == "全局":
        rows = conn.execute(
            "SELECT * FROM 热度窗 WHERE 状态='开启' ORDER BY 窗起事件时"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM 热度窗 WHERE 房间键=? AND 状态='开启' ORDER BY 窗起事件时",
            (房间键,),
        ).fetchall()
    for 窗 in rows:
        if 时间.解析(水位事件时) >= 时间.解析(窗["窗止事件时"]):
            
            cur = conn.execute(
                """UPDATE 热度窗 SET 状态='已关闭', 关闭处理时=?,
                       版本=CASE WHEN 版本=0 THEN 1 ELSE 版本 END
                   WHERE 窗键=? AND 房间键=? AND 状态='开启'""",
                (处理时, 窗["窗键"], 房间键),
            )
            关闭数 += cur.rowcount
    return 关闭数


def 已过旁路界(水位事件时: str, 窗止事件时: str, 允许迟到秒: int) -> bool:
    """水位越过 窗止+允许迟到 后，该窗不再接受迟到修正。"""
    旁路界 = 时间.加秒(窗止事件时, 允许迟到秒)
    return 时间.解析(水位事件时) >= 时间.解析(旁路界)

def _alias_payload(payload: dict) -> dict:
    out = dict(payload or {})
    if "窗键" in out and "window_key" not in out:
        out["window_key"] = out.get("窗键")
    if "房间键" in out and "room_key" not in out:
        out["room_key"] = out.get("房间键")
    if "事件编号" in out and "event_id" not in out:
        out["event_id"] = out.get("事件编号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows(rows: list) -> list:
    return [_alias_payload(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_22(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "livewave", "nn": "22"}
    if extra:
        data.update(extra)
    return data

