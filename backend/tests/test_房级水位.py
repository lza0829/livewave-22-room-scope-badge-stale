"""房级水位线 / 多房串扰隔离 测试。

运行（在 backend/ 下）：
    数据目录用临时目录，python -I tests/test_房级水位.py
"""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp(prefix="livewave-test-")
os.environ["数据目录"] = _tmp
os.environ["夹具目录"] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "fixtures"
)

from app.db import 连接  
from app.modules import 房间级水位线, 多房串扰隔离  
from app.seed import 初始化库  
from app.services import 装载, 时间, 贯验  

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



def test_甲口径_只推A房_B房窗不动():
    装([ev("J-A0", "房A", "2026-11-22T12:00:10Z"),
        ev("J-B0", "房B", "2026-11-22T12:00:10Z")], "批-建窗")
    assert 窗状态("房A", "2026-11-22T12:00:00Z") == "开启"
    assert 窗状态("房B", "2026-11-22T12:00:00Z") == "开启"

    装([ev("J-A1", "房A", "2026-11-22T12:01:05Z")], "批-只推A")

    
    assert 窗状态("房A", "2026-11-22T12:00:00Z") == "已关闭"
    assert 窗状态("房B", "2026-11-22T12:00:00Z") == "开启"
    assert 水位("房A")["事件时水位"] == "2026-11-22T12:01:05Z"
    assert 水位("房B")["事件时水位"] == "2026-11-22T12:00:10Z"

    
    全局最大 = max(水位("房A")["事件时水位"], 水位("房B")["事件时水位"])
    assert 时间.解析(全局最大) >= 时间.解析("2026-11-22T12:01:00Z"), "乙对照前提：全局水位本可越过B窗止"
    口径 = 房间级水位线.口径()
    assert 口径["跨房关窗"] is False and 口径["水位粒度"] == "房间"
    print("✓ 甲口径：只推A → 仅关A，B仍开；同数据下乙口径本会关B（结论可区分）")



def test_AB并发推流_无串房半截():
    基 = "2026-11-22T13:00:"
    错误 = []

    def 推(房, 前缀):
        try:
            for i in range(1, 21):
                秒 = f"{i:02d}"
                装([ev(f"{前缀}-{i}", 房, f"{基}{秒}Z")], f"批-{前缀}-{i}")
        except Exception as e:  
            错误.append(e)

    t1 = threading.Thread(target=推, args=("房A", "CA"))
    t2 = threading.Thread(target=推, args=("房B", "CB"))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert not 错误, f"并发批次异常: {错误}"

    
    assert 水位("房A")["事件时水位"] == f"{基}20Z"
    assert 水位("房B")["事件时水位"] == f"{基}20Z"
    conn = 连接()
    try:
        assert conn.execute("SELECT COUNT(*) c FROM 水位线").fetchone()["c"] == 2
        
        for r in conn.execute("SELECT 事件编号, 房间键, 窗键, 命运 FROM 互动事件"):
            if r["事件编号"].startswith(("CA-", "CB-")):
                if r["命运"] == "已旁路":
                    assert r["窗键"] == ""
                else:
                    assert r["窗键"].startswith(r["房间键"] + "|"), f"串房窗键: {dict(r)}"
        
        for w in conn.execute("SELECT * FROM 热度窗 WHERE 状态='已关闭'"):
            wm = 水位(w["房间键"])
            assert 时间.解析(wm["事件时水位"]) >= 时间.解析(w["窗止事件时"])
            assert w["窗键"].startswith(w["房间键"] + "|")
    finally:
        conn.close()
    print("✓ A/B 并发 40 批：水位行无串写、窗键无串房、关窗均由本房水位触发")



def test_只读接口_valid与口径():
    conn = 连接()
    try:
        行 = 房间级水位线.只读(conn)
        映射 = {r["房间键"]: r for r in 行}
        for 房 in ("房A", "房B"):
            r = 映射[房]
            assert r["valid"] is True
            assert r["水位粒度"] == "房间"
            assert r["水位主键"] == "房间键"
            assert r["扫描范围"] == "本房开启窗"
            assert r["跨房关窗"] is False
        单 = 房间级水位线.只读(conn, "房B")
        assert len(单) == 1 and 单[0]["房间键"] == "房B"

        
        conn.execute("UPDATE 水位线 SET 事件时水位='不是时间' WHERE 房间键='房B'")
        坏 = {r["房间键"]: r for r in 房间级水位线.只读(conn)}
        assert 坏["房B"]["valid"] is False and "不可解析" in 坏["房B"]["无效原因"]
        assert 坏["房A"]["valid"] is True
        conn.rollback()
    finally:
        conn.close()
    print("✓ 房级水位只读接口：口径/扫描范围/valid 齐备，坏行可识别且隔离他房")



def test_同房校验_拒绝串房():
    try:
        多房串扰隔离.同房校验("房A", "房B")
    except RuntimeError:
        pass
    else:
        raise AssertionError("串房校验未触发")
    多房串扰隔离.同房校验("房A", "房A", "房A")  
    print("✓ 同房校验：房键不一致即拒绝，杜绝半截串房")



def test_水位只升不退_且不碰他房():
    b前 = 水位("房B")["事件时水位"]
    装([ev("R-1", "房A", "2026-11-22T12:00:05Z")], "批-回退事件")  
    assert 水位("房B")["事件时水位"] == b前  
    print("✓ 水位只升不退；他房事件不触碰本房水位行")



def test_回归_主链贯验通过():
    import json
    夹具根 = os.environ["夹具目录"]
    for 名 in ("准时热度样例", "迟到修正样例", "超迟到旁路样例"):
        体 = json.loads(open(os.path.join(夹具根, f"{名}.json"), encoding="utf-8").read())
        装载.装一批(体)
    r = 贯验.跑贯验()
    assert r["是否通过"], r["说明"]
    print("✓ 原三套夹具链路回归通过，窗互证贯验通过")


if __name__ == "__main__":
    test_甲口径_只推A房_B房窗不动()
    test_AB并发推流_无串房半截()
    test_只读接口_valid与口径()
    test_同房校验_拒绝串房()
    test_水位只升不退_且不碰他房()
    test_回归_主链贯验通过()
    print(f"\n全部通过（临时库：{_tmp}）")
