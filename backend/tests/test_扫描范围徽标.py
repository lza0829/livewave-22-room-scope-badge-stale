"""扫描范围徽标 / 关窗扫描范围 测试（22 房）。

运行（在 backend/ 下）：
    数据目录用临时目录，python -I tests/test_扫描范围徽标.py

覆盖题面夹具与硬约束：
- 两房都有到期窗只喂一房：甲乙他房均应仍开且徽标为本房；
- 补齐全局工单后再抬升：甲仍不关他房，乙（对照口径）可关他房——本系统选定甲，
  工单仅登记审计、永不扩权；
- 两房并发喂流：不得串写水位行或徽标世代；
- 抬升成功徽标未刷新/徽标与水位行分叉：整票回滚、禁止关窗；
- 陈旧全局徽标：扫描 fail-closed，拒绝出房；
- 核证只读接口：四要素（范围/房键/水位值/世代）可证伪。
"""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="livewave-test-badge-")
os.environ["数据目录"] = _tmp
os.environ["夹具目录"] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "fixtures"
)

from app.db import 连接
from app.modules import 扫描范围徽标, 房间级水位线
from app.seed import 初始化库
from app.services import 装载, 时间

初始化库()


def 装(事件, 批):
    return 装载.装一批({"批次编号": 批, "事件": 事件})


def ev(编号, 房, 事件时, 赞=1, 处理时=None):
    return {
        "事件编号": 编号,
        "房间键": 房,
        "事件类型": "点赞",
        "事件时": 事件时,
        "处理时": 处理时 or 事件时,
        "观众键": f"观-{编号}",
        "点赞增量": 赞,
        "送礼额": 0,
    }


def 窗状态(房, 窗起):
    conn = 连接()
    try:
        r = conn.execute(
            "SELECT 状态 FROM 热度窗 WHERE 窗键=?", (时间.窗键(房, 窗起),)
        ).fetchone()
        return r["状态"] if r else None
    finally:
        conn.close()


def 水位(房):
    conn = 连接()
    try:
        return conn.execute(
            "SELECT * FROM 水位线 WHERE 房间键=?", (房,)
        ).fetchone()
    finally:
        conn.close()


def 最新徽标(房):
    conn = 连接()
    try:
        return 扫描范围徽标.取最新徽标(conn, 房)
    finally:
        conn.close()


def 核证(房=None):
    conn = 连接()
    try:
        return 扫描范围徽标.查徽标(conn, 房)
    finally:
        conn.close()


def 建两房窗():
    """两房各建 12:00:00–12:01:00 开启窗（窗止均可被 12:01:05 越过）。"""
    装([ev("B-A0", "房A", "2026-11-22T12:00:10Z"),
        ev("B-B0", "房B", "2026-11-22T12:00:20Z")], "批-建窗")


def test_两房到期窗_只喂一房_他房仍开且徽标本房():
    建两房窗()
    assert 窗状态("房A", "2026-11-22T12:00:00Z") == "开启"
    assert 窗状态("房B", "2026-11-22T12:00:00Z") == "开启"

    装([ev("B-A1", "房A", "2026-11-22T12:01:05Z")], "批-只推A")

    # 甲口径：仅 A 关，B 仍开（乙对照口径下 B 也会被关——本系统禁止）
    assert 窗状态("房A", "2026-11-22T12:00:00Z") == "已关闭"
    assert 窗状态("房B", "2026-11-22T12:00:00Z") == "开启", "只推A房不得关B房窗"

    # 两房徽标均钉本房，四要素与各自水位行一致
    for 房, 期望水位 in (("房A", "2026-11-22T12:01:05Z"),
                        ("房B", "2026-11-22T12:00:20Z")):
        徽 = 最新徽标(房)
        assert 徽["范围"] == "本房", f"{房}徽标必须为本房范围"
        assert 徽["房间键"] == 房
        assert 徽["水位值"] == 期望水位, f"{房}徽标水位值必须等于本房水位行"
        assert 徽["水位值"] == 水位(房)["事件时水位"]
        assert int(徽["徽标世代"]) >= 1

    证 = 核证()
    assert 证["设计取舍"] == "事件房键钉本房徽标"
    assert 证["范围"] == "本房" and 证["采信徽标"] is True
    映射 = {r["房间键"]: r for r in 证["核证"]}
    assert 映射["房A"]["valid"] and 映射["房B"]["valid"]
    assert 映射["房A"]["采信徽标"] and 映射["房B"]["采信徽标"]
    print("✓ 两房到期窗只喂A：仅A关、B仍开；两房徽标均钉本房且四要素核证通过")


def test_全局工单齐套_仍不扩权_甲乙都不关他房():
    # 登记「全局切换工单」（对照口径乙的齐套凭证）
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        工单 = 扫描范围徽标.登记全局工单(conn, "WO-GLOBAL-1", "房A")
        conn.commit()
    finally:
        conn.close()
    assert 工单["状态"] == "登记"

    # 甲再抬升（越过窗止）：工单存在也不得改全局、不得关他房
    装([ev("B-A2", "房A", "2026-11-22T12:01:30Z")], "批-工单后抬甲")
    assert 最新徽标("房A")["范围"] == "本房", "工单不得把徽标改成全局"
    assert 窗状态("房B", "2026-11-22T12:00:00Z") == "开启", "甲持工单也不得关乙房窗"

    # 乙自己抬升越过窗止：只能关乙本房窗，仍不能扫甲房
    装([ev("B-B1", "房B", "2026-11-22T12:01:10Z")], "批-抬乙")
    assert 最新徽标("房B")["范围"] == "本房"
    assert 窗状态("房B", "2026-11-22T12:00:00Z") == "已关闭", "乙抬升只关乙本房窗"
    # A 房窗此前已由 A 自己关闭；没有任何跨房关闭动作（B 的扫描未触碰 A）
    assert 窗状态("房A", "2026-11-22T12:00:00Z") == "已关闭"

    证 = 核证()
    assert 证["工单可扩权"] is False
    assert len(证["全局切换工单"]) == 1 and 证["全局切换工单"][0]["工单号"] == "WO-GLOBAL-1"
    assert all(r["范围"] == "本房" for r in 证["核证"])
    print("✓ 全局工单齐套仍不扩权：甲不关乙、乙只关本房；工单仅留痕审计")


def test_两房并发喂流_不串水位行_不串徽标世代():
    基 = "2026-11-22T14:00:"
    错误 = []

    def 推(房, 前缀):
        try:
            for i in range(1, 21):
                装([ev(f"{前缀}-{i}", 房, f"{基}{i:02d}Z")], f"批-{前缀}-{i}")
        except Exception as e:
            错误.append(e)

    t1 = threading.Thread(target=推, args=("房A", "DA"))
    t2 = threading.Thread(target=推, args=("房B", "DB"))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert not 错误, f"并发批次异常: {错误}"

    # 水位行各写各的，仍是两行且房键正确
    assert 水位("房A")["事件时水位"] == f"{基}20Z"
    assert 水位("房B")["事件时水位"] == f"{基}20Z"
    conn = 连接()
    try:
        assert conn.execute("SELECT COUNT(*) c FROM 水位线").fetchone()["c"] == 2
        # 徽标行：每行房键与水位值必须与同房水位行严格对齐，世代按房连续
        for 房 in ("房A", "房B"):
            行们 = conn.execute(
                "SELECT * FROM 扫描范围徽标 WHERE 房间键=? ORDER BY 徽标世代", (房,)
            ).fetchall()
            assert 行们, f"{房}缺徽标行"
            世代们 = [int(r["徽标世代"]) for r in 行们]
            assert 世代们 == list(range(0, len(世代们))), f"{房}徽标世代不连续: {世代们}"
            for r in 行们:
                assert r["房间键"] == 房, "徽标行串房"
                assert r["范围"] == "本房", "并发下出现非本房徽标"
            # 最新徽标水位值 == 本房水位行
            末 = 行们[-1]
            wm = conn.execute(
                "SELECT 事件时水位 FROM 水位线 WHERE 房间键=?", (房,)
            ).fetchone()
            assert 末["水位值"] == wm["事件时水位"], "徽标水位值与水位行错位"
        # 本并发时段（14:00）每房徽标行的水位值必须逐行等于同房水位行当时取值，
        # 且每行房键/范围正确——串写（A房徽标挂B房行）在房键绑定下即被抓住
        for 房 in ("房A", "房B"):
            行们 = conn.execute(
                "SELECT * FROM 扫描范围徽标 WHERE 房间键=? AND 水位值 LIKE '2026-11-22T14:00:%' ORDER BY 徽标世代",
                (房,),
            ).fetchall()
            assert len(行们) == 20, f"{房}并发20次抬升应留20行本时段徽标，实得{len(行们)}"
            assert all(r["房间键"] == 房 and r["范围"] == "本房" for r in 行们)
        # 事件窗键仍带本房前缀
        for r in conn.execute("SELECT 事件编号, 房间键, 窗键, 命运 FROM 互动事件"):
            if r["事件编号"].startswith(("DA-", "DB-")):
                if r["命运"] == "已旁路":
                    assert r["窗键"] == ""
                else:
                    assert r["窗键"].startswith(r["房间键"] + "|"), f"串房窗键: {dict(r)}"
    finally:
        conn.close()
    print("✓ A/B 并发 40 批：水位行无串写、徽标世代按房连续无串房、四要素对齐")


def test_徽标刷新失败_整票回滚_水位与关窗同撤():
    conn = 连接()
    try:
        前水位 = 水位("房A")["事件时水位"]
        前批数 = conn.execute("SELECT COUNT(*) c FROM 装载批次").fetchone()["c"]
    finally:
        conn.close()

    原刷 = 扫描范围徽标.同票刷徽标

    def 炸刷(*a, **k):
        raise RuntimeError("模拟徽标刷新失败")

    扫描范围徽标.同票刷徽标 = 炸刷
    扫描范围徽标.尝试刷徽标 = 炸刷
    try:
        try:
            装([ev("B-FAIL", "房A", "2026-11-22T15:00:05Z")], "批-徽标失败")
        except RuntimeError as e:
            assert "徽标刷新失败" in str(e)
        else:
            raise AssertionError("徽标刷新失败必须上抛，不得吞异常")
    finally:
        扫描范围徽标.同票刷徽标 = 原刷
        扫描范围徽标.尝试刷徽标 = 原刷

    # 整票回滚：水位未抬、事件未入、批次未记
    assert 水位("房A")["事件时水位"] == 前水位, "徽标失败时本房水位写入必须随票回滚"
    conn = 连接()
    try:
        assert conn.execute(
            "SELECT 1 FROM 互动事件 WHERE 事件编号=?", ("B-FAIL",)
        ).fetchone() is None
        assert conn.execute(
            "SELECT COUNT(*) c FROM 装载批次"
        ).fetchone()["c"] == 前批数
        assert 窗状态("房A", "2026-11-22T15:00:00Z") is None  # 窗也没建出来
    finally:
        conn.close()
    print("✓ 徽标刷新失败：异常上抛、整票回滚，水位/事件/关窗无一半截落库")


def test_陈旧全局徽标_扫描拒绝_不得出房关窗():
    # 人为植入陈旧全局徽标（模拟历史脏数据），扫描必须 fail-closed
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        旧 = 扫描范围徽标.取最新徽标(conn, "房A")
        conn.execute(
            "INSERT INTO 扫描范围徽标(房间键, 范围, 水位值, 徽标世代, 时刻) VALUES (?,?,?,?,?)",
            ("房A", "全局", "2026-11-22T16:00:00Z", int(旧["徽标世代"]) + 1, "2026-11-22T16:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()

    # 核证接口应识别为不可采信
    证 = 核证("房A")
    单 = 证["核证"][0]
    assert 单["valid"] is False and 单["采信徽标"] is False
    assert "非本房" in 单["无效原因"]

    # 下一次抬升同票把徽标刷回本房；刷回前扫描器拒绝出房
    conn = 连接()
    try:
        try:
            扫描范围徽标.扫描范围(conn, "房A")
        except RuntimeError as e:
            assert "非本房" in str(e)
        else:
            raise AssertionError("全局徽标下扫描必须拒绝")
    finally:
        conn.close()

    装([ev("B-HEAL", "房A", "2026-11-22T16:00:10Z")], "批-刷回徽标")
    徽 = 最新徽标("房A")
    assert 徽["范围"] == "本房" and 徽["水位值"] == "2026-11-22T16:00:10Z"
    # 刷回后扫描恢复，且只扫本房，B 房窗不受影响
    assert 窗状态("房B", "2026-11-22T12:00:00Z") == "已关闭"  # 前序测试中 B 自关
    print("✓ 陈旧全局徽标：核证判伪、扫描 fail-closed；抬升同票刷回本房后恢复")


def test_徽标与水位行分叉_扫描拒绝():
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        旧 = 扫描范围徽标.取最新徽标(conn, "房B")
        # 房键仍是房B、范围本房，但水位值与水位行不一致（陈旧徽标）
        conn.execute(
            "INSERT INTO 扫描范围徽标(房间键, 范围, 水位值, 徽标世代, 时刻) VALUES (?,?,?,?,?)",
            ("房B", "本房", "2026-11-22T09:00:00Z", int(旧["徽标世代"]) + 1, "2026-11-22T09:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()

    证 = 核证("房B")
    assert 证["核证"][0]["valid"] is False
    assert "陈旧" in 证["核证"][0]["无效原因"]
    conn = 连接()
    try:
        try:
            扫描范围徽标.扫描范围(conn, "房B")
        except RuntimeError as e:
            assert "分叉" in str(e) or "陈旧" in str(e)
        else:
            raise AssertionError("徽标水位值与水位行分叉必须拒绝扫描")
    finally:
        conn.close()

    # 房级水位只读接口同步暴露徽标 invalid
    conn = 连接()
    try:
        行 = {r["房间键"]: r for r in 房间级水位线.只读(conn)}
        assert 行["房B"]["徽标valid"] is False
        assert "陈旧" in 行["房B"]["徽标无效原因"]
    finally:
        conn.close()

    # 下次 B 房抬升自动刷齐
    装([ev("B-HEAL2", "房B", "2026-11-22T16:01:05Z")], "批-B刷齐")
    assert 最新徽标("房B")["水位值"] == 水位("房B")["事件时水位"]
    print("✓ 徽标/水位行分叉：核证与房级水位双接口判伪、扫描拒绝；抬升后刷齐")


def test_空徽标与同房同水位幂等():
    # 空徽标：删掉房A全部徽标行后，扫描必须拒绝（不回退全局）
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM 扫描范围徽标 WHERE 房间键='房A'")
        conn.commit()
    finally:
        conn.close()
    conn = 连接()
    try:
        try:
            扫描范围徽标.扫描范围(conn, "房A")
        except RuntimeError as e:
            assert "缺失" in str(e)
        else:
            raise AssertionError("空徽标不得扫描")
    finally:
        conn.close()

    # 幂等：同房同水位重复刷，不新增世代
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        扫描范围徽标.确保房徽标行(conn, "房A", 水位("房A")["事件时水位"])
        前世代 = int(扫描范围徽标.取最新徽标(conn, "房A")["徽标世代"])
        扫描范围徽标.同票刷徽标(conn, "房A", 水位("房A")["事件时水位"])
        扫描范围徽标.同票刷徽标(conn, "房A", 水位("房A")["事件时水位"])
        后世代 = int(扫描范围徽标.取最新徽标(conn, "房A")["徽标世代"])
        conn.commit()
    finally:
        conn.close()
    assert 前世代 == 后世代, "同房同水位刷新必须幂等"
    print("✓ 空徽标 fail-closed（不回退全局）；同房同水位刷新幂等不涨世代")


if __name__ == "__main__":
    test_两房到期窗_只喂一房_他房仍开且徽标本房()
    test_全局工单齐套_仍不扩权_甲乙都不关他房()
    test_两房并发喂流_不串水位行_不串徽标世代()
    test_徽标刷新失败_整票回滚_水位与关窗同撤()
    test_陈旧全局徽标_扫描拒绝_不得出房关窗()
    test_徽标与水位行分叉_扫描拒绝()
    test_空徽标与同房同水位幂等()
    print(f"\n全部通过（临时库：{_tmp}）")
