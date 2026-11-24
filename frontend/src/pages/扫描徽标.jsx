import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 扫描徽标() {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const reload = () => {
    取("/核证/扫描徽标").then(setRows).catch((e) => setErr(String(e.message || e)));
  };
  useEffect(() => { reload(); }, []);
  return (
    <div>
      <h1 className="题">扫描徽标核证</h1>
      <p className="述">
        关窗扫描只采信本房扫描范围徽标。房级抬升成功必须同票刷新徽标四要素（范围、房键、水位值、徽标世代），
        半截失败整票回滚；徽标缺失/陈旧/范围非本房时扫描 fail-closed，禁止出房关窗。
      </p>
      {rows && (
        <div className="提示条">
          全局设计取舍＝<strong>{rows.设计取舍}</strong>；声明范围＝<strong>{rows.范围}</strong>
          ；整体采信徽标＝<strong>{rows.采信徽标 ? "是" : "否"}</strong>
          ；全局切换工单可扩权＝<strong>{rows.工单可扩权 ? "是" : "否（仅登记审计）"}</strong>
          <div style={{ marginTop: 6 }}>{rows.对照取舍}</div>
        </div>
      )}
      {err && <pre className="码">{err}</pre>}
      <button className="次" onClick={reload}>刷新</button>

      {rows && (
        <div className="段">
          <div className="段题">每房徽标核证（范围 / 房键 / 水位值 / 世代）</div>
          <table>
            <thead>
              <tr>
                <th>房间</th><th>徽标范围</th><th>徽标世代</th><th>徽标水位值</th>
                <th>水位行水位</th><th>采信</th><th>无效原因</th>
              </tr>
            </thead>
            <tbody>
              {rows.核证.map((r) => (
                <tr key={r.房间键}>
                  <td>{r.房间键}</td>
                  <td>{r.范围 || "—"}</td>
                  <td>{r.徽标世代 ?? "—"}</td>
                  <td className="码">{r.徽标水位值 || "—"}</td>
                  <td className="码">{r.水位行水位 || "—"}</td>
                  <td>{r.采信徽标 ? "✓ 采信" : "✗ 拒绝"}</td>
                  <td>{r.无效原因 || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows && rows.全局切换工单?.length > 0 && (
        <div className="段">
          <div className="段题">全局切换工单（审计留痕，永不扩权）</div>
          <table>
            <thead><tr><th>工单号</th><th>房间</th><th>状态</th><th>处置</th><th>时刻</th></tr></thead>
            <tbody>
              {rows.全局切换工单.map((t) => (
                <tr key={t.工单号}>
                  <td className="码">{t.工单号}</td><td>{t.房间键 || "—"}</td>
                  <td>{t.状态}</td><td>{t.处置}</td><td className="码">{t.时刻}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="段">
        <div className="段题">徽标历史（追加式，最近 50 行）</div>
        <pre className="码">{rows ? JSON.stringify(rows.徽标, null, 2) : "（空）"}</pre>
      </div>
    </div>
  );
}
