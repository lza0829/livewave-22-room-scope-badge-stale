"""水位线只读辅助。

写入口已统一收归 app.modules.房间级水位线（确保房水位行/按房键条件推进），
本模块仅保留按房键读取，禁止在此另开写入路径，避免绕过隔离口径。
"""


def 读(conn, 房间键: str):
    return conn.execute("SELECT * FROM 水位线 WHERE 房间键=?", (房间键,)).fetchone()

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

