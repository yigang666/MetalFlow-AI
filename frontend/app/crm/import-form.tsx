"use client";

import { useState, useTransition } from "react";
import type { FormEvent } from "react";
import { importCustomers } from "./actions";
import type { ImportState } from "./actions";

const initial: ImportState = { phase: "idle", rows: [] };
const statuses = {
  ready: "可导入",
  duplicate: "疑似重复",
  invalid: "需修正",
  created: "已创建",
};

export default function ImportForm() {
  const [state, setState] = useState(initial);
  const [pending, startTransition] = useTransition();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const commit = form.get("mode") === "commit";
    startTransition(async () => {
      try {
        const result = await importCustomers(form, commit ? state.proof : undefined);
        setState(commit && result.error ? { ...state, error: result.error } : result);
      } catch {
        const error = "导入请求失败，请重试。";
        setState(commit ? { ...state, error } : { ...initial, error });
      }
    });
  }
  return (
    <section className="card" aria-labelledby="import-title">
      <h2 id="import-title">Excel 导入</h2>
      <p className="mt-2 muted">
        工作表名为 <code>Customers</code>，最多 500 条数据，文件大小上限 2 MiB。表头按以下顺序填写。
      </p>
      <p className="mt-2 overflow-x-auto"><code>name,country,website,contact_name,email,phone,linkedin_url</code></p>
      {state.error && <p className="notice mt-4" role="alert">{state.error}</p>}
      <form onSubmit={submit} className="mt-4 grid gap-3" aria-label="预览 Excel 导入">
        <input type="hidden" name="mode" value="preview" />
        <label className="field">
          Excel 文件
          <input type="file" name="file" accept=".xlsx" required />
        </label>
        <div><button className="button-secondary" type="submit" disabled={pending}>预览导入</button></div>
      </form>
      {state.phase !== "idle" && (
        <form onSubmit={submit} className="mt-5 grid gap-4" aria-label="核对 Excel 导入">
          <input type="hidden" name="mode" value="commit" />
          <h3 className="font-semibold">
            {state.phase === "preview" ? "导入预览" : "导入结果"}
          </h3>
          {state.phase === "committed" && (
            <p role="status">
              已创建 {state.rows.filter((row) => row.status === "created").length} 条客户记录。
              {state.replayed && " 已展示此前提交的结果。"}
            </p>
          )}
          {state.rows.length === 0 && <p className="muted" role="status">工作簿中暂无客户行。</p>}
          {state.rows.length > 0 && (
            <div className="overflow-x-auto">
              <table aria-label={state.phase === "preview" ? "导入预览" : "导入结果"}>
                <thead><tr><th scope="col">行</th><th scope="col">客户</th><th scope="col">状态</th><th scope="col">核对事项</th></tr></thead>
                <tbody>
                  {state.rows.map((row) => (
                    <tr key={row.row}>
                      <td>{row.row}</td>
                      <td>{row.name || "—"}</td>
                      <td>{statuses[row.status]}</td>
                      <td>
                        {row.errors.length > 0 && <p>{row.errors.join("；")}</p>}
                        {row.matches.length > 0 && <p>可能匹配 {row.matches.map((match) => match.name).join("、")}</p>}
                        {row.status === "duplicate" && state.phase === "preview" && (
                          <label className="inline-flex items-center gap-2">
                            <input type="checkbox" name="confirm_row" value={row.row} />
                            第 {row.row} 行作为独立客户创建
                          </label>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {state.phase === "preview" && state.rows.some((row) => row.status === "ready" || row.status === "duplicate") && (
            <>
              <p className="muted">核对后重新选择同一份工作簿。未勾选的疑似重复行将跳过。</p>
              <label className="field">
                确认文件
                <input type="file" name="file" accept=".xlsx" required />
              </label>
              <div><button className="button-primary" type="submit" disabled={pending}>确认导入</button></div>
            </>
          )}
        </form>
      )}
      {pending && <p className="mt-3 muted" role="status">正在处理工作簿…</p>}
    </section>
  );
}
