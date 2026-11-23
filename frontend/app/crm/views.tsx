const statuses: Record<string, string> = {
  saved: "已保存。",
  forbidden: "当前账户无此操作权限。",
  invalid: "请检查输入内容后重试。",
  origin: "请从配置的 Sandbox 地址提交表单。",
  notfound: "该客户或记录不存在，或当前账户无法访问。",
  unavailable: "服务暂不可用，请稍后重试。",
};

export function CrmNotice({ status }: { status?: string }) {
  if (!status || !Object.hasOwn(statuses, status)) return null;
  const allowed = status === "saved";
  return <p className={allowed ? "crm-success" : "notice"} role={allowed ? "status" : "alert"}>{statuses[status]}</p>;
}
