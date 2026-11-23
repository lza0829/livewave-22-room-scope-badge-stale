import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 水位线页() {
  const [视图, 设视图] = useState(null);
  const 刷 = () => 取("/房级水位").then(设视图);
  useEffect(() => { 刷(); }, []);
  const 口径 = 视图?.隔离口径;
  const 房 = 视图?.房级水位 || [];
  return (
    <div>
      <h1 className="题">② 水位线（房间级）</h1>
      <p className="述">
        每房一条<strong>事件时水位</strong>（已见最大事件时）。规则：水位 ≥ 窗止 → 关窗发射；水位 ≥ 窗止 + 允许迟到 → 该窗拒收迟到（进旁路）。
      </p>
      {口径 && (
        <div className="提示条">
          全局隔离口径＝<strong>{口径.隔离口径}</strong>（主键：{口径.水位主键}；扫描范围：{口径.扫描范围}
          ；跨房关窗：{口径.跨房关窗 ? "是" : "否"}）。只推 A 房事件时：{口径.只推A房时B房窗}
        </div>
      )}
      <div className="行"><button className="次" onClick={刷}>刷新水位</button></div>
      {!房.length ? (
        <div className="空态">无直播间</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>房间</th><th>事件时水位</th><th>允许迟到秒</th><th>水位更新处理时</th>
              <th>扫描范围</th><th>valid</th>
            </tr>
          </thead>
          <tbody>
            {房.map((r) => (
              <tr key={r.房间键}>
                <td>{r.房间键}</td>
                <td className="码">{r.事件时水位 || "—"}</td>
                <td>{r.允许迟到秒 ?? "—"}</td>
                <td className="码">{r.更新处理时 || "—"}</td>
                <td>{r.扫描范围}</td>
                <td>
                  {r.valid ? "✓ valid" : `✗ ${r.无效原因 || "invalid"}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
