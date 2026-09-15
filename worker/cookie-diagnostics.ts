// Public, non-authenticating markers. Never read OAuth or Substack credentials here.
const HOST_MARKER = "__Host-SUBSTACK_MCP_DIAGNOSTIC";
const PLAIN_MARKER = "SUBSTACK_MCP_DIAGNOSTIC";
const headers = {
  "Cache-Control": "no-store, max-age=0",
  Pragma: "no-cache",
  "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Frame-Options": "DENY",
};

function page(content: string): Response {
  return new Response(`<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Substack MCP 接続診断</title></head><body style="font-family:system-ui;max-width:640px;margin:40px auto;padding:24px;line-height:1.7"><h1>Substack MCP 接続診断</h1>${content}</body></html>`, {
    headers: { ...headers, "Content-Type": "text/html; charset=utf-8" },
  });
}

export function cookieDiagnostics(request: Request): Response {
  if (new URL(request.url).pathname === "/auth/diagnostics") {
    const response = page(`<p>認証には使えない診断用Cookieを2種類発行しました。有効期限は2分です。</p>
<p>下のリンクとボタンでCookieが届くか比較できます。記事の取得・投稿やアカウント接続は行いません。</p>
<p><a href="/auth/diagnostics/check">リンクで確認する（GET）</a></p>
<form method="post" action="/auth/diagnostics/check"><button type="submit">フォームで確認する（POST）</button></form>
<p>どちらも確認する場合は、結果画面の「診断を開始し直す」から戻ってください。</p>`);
    for (const name of [HOST_MARKER, PLAIN_MARKER]) {
      response.headers.append("Set-Cookie", `${name}=1; HttpOnly; Secure; Path=/; SameSite=Lax; Max-Age=120`);
    }
    return response;
  }

  const cookies = (request.headers.get("Cookie") ?? "").split(";").map((part) => part.trim());
  const result = {
    method: request.method,
    host_cookie_received: cookies.includes(`${HOST_MARKER}=1`),
    plain_cookie_received: cookies.includes(`${PLAIN_MARKER}=1`),
  };
  if (!request.headers.get("Accept")?.includes("text/html")) {
    return Response.json(result, { headers });
  }
  const label = (received: boolean) => received ? "到達" : "未到達";
  return page(`<h2>${result.method}の結果</h2>
<ul><li>制約付きCookie（__Host-）: <strong>${label(result.host_cookie_received)}</strong></li>
<li>通常名のCookie: <strong>${label(result.plain_cookie_received)}</strong></li></ul>
<p>この結果は診断用Cookieの到達だけを示します。OAuth接続の成功や、Cookie未到達の原因を確定するものではありません。</p>
<p><a href="/auth/diagnostics">診断を開始し直す</a></p>`);
}
