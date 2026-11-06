export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = sessionStorage.getItem("deskmate.token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(0, "暂时连接不上桌伴服务，请确认后端已启动后重试。");
  }
  const assertCurrentSession = () => {
    if (
      path !== "/api/auth/login" &&
      token !== sessionStorage.getItem("deskmate.token")
    )
      throw new DOMException("会话已切换", "AbortError");
  };
  assertCurrentSession();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    assertCurrentSession();
    if (response.status === 401 && path !== "/api/auth/login")
      window.dispatchEvent(new Event("deskmate:unauthorized"));
    throw new ApiError(
      response.status,
      typeof body.detail === "string"
        ? body.detail
        : `请求未完成（${response.status}），请检查输入后重试。`,
    );
  }
  const value = (await response.json()) as T;
  assertCurrentSession();
  return value;
}
export const post = <T>(path: string, body?: unknown, signal?: AbortSignal) =>
  request<T>(path, {
    method: "POST",
    body: JSON.stringify(body ?? {}),
    signal,
  });
export function today(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
export function download(
  name: string,
  content: string,
  mime = "text/markdown;charset=utf-8",
) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
