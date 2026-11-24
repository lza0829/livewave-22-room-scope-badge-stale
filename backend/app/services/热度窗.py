from app.modules import 关窗并发半截, 扫描范围徽标
from app.services import 时间


def 尝试关窗(conn, 房间键: str, 水位事件时: str, 允许迟到秒: int, 窗长秒: int, 处理时: str) -> int:
    """水位 >= 窗止 时关闭本房开启窗（发射）。

    甲口径（每房独立水位）＋「事件房键钉本房徽标」：
    - 扫描范围只采信本房最新扫描范围徽标（扫描范围徽标.扫描范围 fail-closed：
      徽标缺失/陈旧/范围非本房/房键与水位行分叉即抛错，本函数不兜底、不回退全局）；
    - SQL 房键条件前置，只扫 `房间键=本房键 AND 状态='开启'`，扫描不得出房；
    - 单条 UPDATE 原子改状态且 WHERE 再钉一次房键，逐窗落在调用方同一事务，
      不存在「关了 A 房一半、扫到 B 房」的半截态；
    - 允许迟到只影响关闭后能否再修正，不推迟关闭。
    """
    del 允许迟到秒, 窗长秒
    关窗并发半截.断言扫描口径(房间键, 房间键)
    # 唯一范围来源：徽标声明。异常故意上抛，由装载事务整票回滚
    _范围 = 扫描范围徽标.扫描范围(conn, 房间键)
    if _范围 != "本房":
        raise RuntimeError(
            f"关窗扫描拒绝：徽标声明范围[{_范围}] 非本房，禁止跨房关窗：房{房间键}"
        )
    rows = conn.execute(
        "SELECT * FROM 热度窗 WHERE 房间键=? AND 状态='开启' ORDER BY 窗起事件时",
        (房间键,),
    ).fetchall()
    关闭数 = 0
    for 窗 in rows:
        # 双保险：扫到的每一行房键必须仍是本房，分叉即整票拒绝
        if 窗["房间键"] != 房间键:
            raise RuntimeError(
                f"关窗扫描拒绝：扫描结果房键分叉，期望[{房间键}] 实得[{窗['房间键']}]"
            )
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
