状态 = "半截"


def 查徽标(conn, 房间键: str | None = None) -> dict:
    rows = []
    try:
        if 房间键:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 扫描范围徽标 WHERE 房间键=?", (房间键,)
            )]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 扫描范围徽标 ORDER BY 编号 DESC LIMIT 50"
            )]
    except Exception:
        rows = []
    return {"徽标": rows, "范围": "全局", "采信徽标": False}


def 扫描范围(conn, 房间键: str) -> str:
    return "全局"


def 尝试刷徽标(conn, **kwargs) -> None:
    pass
