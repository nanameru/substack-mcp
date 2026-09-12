import type {
  AuthRequest,
  OAuthHelpers,
} from "@cloudflare/workers-oauth-provider";

import type { Env } from "./types";

type OAuthEnv = Env & { OAUTH_PROVIDER: OAuthHelpers };

const CSRF_COOKIE_PREFIX = "__Host-SUBSTACK_MCP_CSRF_";
const STATE_COOKIE_PREFIX = "__Host-SUBSTACK_MCP_STATE_";

function jsonError(message: string, status = 400): Response {
  return Response.json({ error: message }, { status });
}

function cookieValue(request: Request, name: string): string | null {
  const cookies = (request.headers.get("Cookie") ?? "").split(";");
  for (const part of cookies) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

function secureCookie(name: string, value: string, maxAge: number): string {
  return `${name}=${value}; HttpOnly; Secure; Path=/; SameSite=Lax; Max-Age=${maxAge}`;
}

function flowCookieName(prefix: string, token: string): string {
  const suffix = token.replace(/[^a-z0-9]/gi, "").slice(0, 64);
  return `${prefix}${suffix || "invalid"}`;
}

async function sha256(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function encodeState(value: unknown): string {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function decodeState(value: string): AuthRequest {
  const binary = atob(value);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes)) as AuthRequest;
}

function isAllowed(login: string, env: Env): boolean {
  return env.ALLOWED_GITHUB_LOGINS.split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .includes(login.toLowerCase());
}

async function authorizeGet(request: Request, env: OAuthEnv): Promise<Response> {
  let authRequest: AuthRequest;
  try {
    authRequest = await env.OAUTH_PROVIDER.parseAuthRequest(request);
  } catch {
    return jsonError("Invalid OAuth request");
  }

  const client = await env.OAUTH_PROVIDER.lookupClient(authRequest.clientId);
  if (!client) return jsonError("Unknown OAuth client");

  const csrf = crypto.randomUUID();
  const csrfCookie = flowCookieName(CSRF_COOKIE_PREFIX, csrf);
  const clientName = escapeHtml(client.clientName || "ChatGPT");
  const state = escapeHtml(encodeState(authRequest));

  const html = `<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Substack MCPを接続</title></head>
<body style="font-family:system-ui;max-width:560px;margin:48px auto;padding:24px;line-height:1.6">
<h1>Substack MCPを接続</h1>
<p><strong>${clientName}</strong> が、あなたのSubstack下書き・公開・予約ツールへのアクセスを求めています。</p>
<p>続行するとGitHubで本人確認します。許可されたGitHubアカウントだけが接続できます。</p>
<form method="post" action="/authorize">
<input type="hidden" name="csrf_token" value="${csrf}">
<input type="hidden" name="state" value="${state}">
<button type="submit" style="font:inherit;padding:10px 18px">GitHubで確認して許可</button>
</form></body></html>`;

  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' https://github.com/login/oauth/authorize; base-uri 'none'; frame-ancestors 'none'",
      "Referrer-Policy": "no-referrer",
      "X-Frame-Options": "DENY",
      "Set-Cookie": secureCookie(csrfCookie, csrf, 600),
    },
  });
}

async function authorizePost(request: Request, env: OAuthEnv): Promise<Response> {
  const form = await request.formData();
  const csrfForm = form.get("csrf_token");
  const encoded = form.get("state");
  const csrfCookie =
    typeof csrfForm === "string"
      ? cookieValue(request, flowCookieName(CSRF_COOKIE_PREFIX, csrfForm))
      : null;
  if (typeof csrfForm !== "string" || !csrfCookie || csrfForm !== csrfCookie) {
    return jsonError("Invalid CSRF token");
  }
  if (typeof encoded !== "string") return jsonError("Missing OAuth state");

  let authRequest: AuthRequest;
  try {
    authRequest = decodeState(encoded);
  } catch {
    return jsonError("Invalid OAuth state");
  }

  const state = crypto.randomUUID();
  await env.OAUTH_KV.put(`state:${state}`, JSON.stringify(authRequest), {
    expirationTtl: 600,
  });
  const stateHash = await sha256(state);
  const stateCookie = flowCookieName(STATE_COOKIE_PREFIX, state);
  const callback = new URL("/callback", request.url).href;
  const github = new URL("https://github.com/login/oauth/authorize");
  github.searchParams.set("client_id", env.GITHUB_CLIENT_ID);
  github.searchParams.set("redirect_uri", callback);
  github.searchParams.set("scope", "read:user");
  github.searchParams.set("state", state);

  const headers = new Headers({ Location: github.href });
  headers.append(
    "Set-Cookie",
    secureCookie(flowCookieName(CSRF_COOKIE_PREFIX, csrfForm), "", 0),
  );
  headers.append("Set-Cookie", secureCookie(stateCookie, stateHash, 600));
  return new Response(null, { status: 302, headers });
}

async function callback(request: Request, env: OAuthEnv): Promise<Response> {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  if (!code || !state) return jsonError("Missing GitHub OAuth response");

  const stateCookie = flowCookieName(STATE_COOKIE_PREFIX, state);
  const expectedHash = cookieValue(request, stateCookie);
  if (!expectedHash || (await sha256(state)) !== expectedHash) {
    return jsonError("OAuth state does not match this browser session");
  }

  const stored = await env.OAUTH_KV.get(`state:${state}`);
  await env.OAUTH_KV.delete(`state:${state}`);
  if (!stored) return jsonError("OAuth state expired");

  const tokenResponse = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: env.GITHUB_CLIENT_ID,
      client_secret: env.GITHUB_CLIENT_SECRET,
      code,
      redirect_uri: new URL("/callback", request.url).href,
    }),
  });
  if (!tokenResponse.ok) return jsonError("GitHub token exchange failed", 502);
  const tokenData = (await tokenResponse.json()) as {
    access_token?: string;
    error?: string;
  };
  if (!tokenData.access_token) {
    // GitHub commonly returns HTTP 200 with a machine-readable OAuth error.
    // Surface only that non-secret error code so credential/configuration issues
    // can be distinguished without logging the authorization code or secrets.
    const oauthError = tokenData.error?.replace(/[^a-z0-9_]/gi, "").slice(0, 80);
    return jsonError(
      oauthError
        ? `GitHub token exchange failed: ${oauthError}`
        : "GitHub did not return an access token",
      502,
    );
  }

  const userResponse = await fetch("https://api.github.com/user", {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${tokenData.access_token}`,
      "User-Agent": "substack-mcp-cloudflare",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!userResponse.ok) return jsonError("GitHub identity lookup failed", 502);
  const user = (await userResponse.json()) as { login?: string };
  if (!user.login || !isAllowed(user.login, env)) {
    return jsonError("This GitHub account is not allowed to use this MCP server", 403);
  }

  const authRequest = JSON.parse(stored) as AuthRequest;
  const { redirectTo } = await env.OAUTH_PROVIDER.completeAuthorization({
    request: authRequest,
    userId: user.login,
    metadata: { label: `Substack MCP (${user.login})` },
    scope: authRequest.scope,
    props: { login: user.login },
  });

  return new Response(null, {
    status: 302,
    headers: {
      Location: redirectTo,
      "Set-Cookie": secureCookie(stateCookie, "", 0),
    },
  });
}

export const authHandler: ExportedHandler<OAuthEnv> = {
  async fetch(request, env): Promise<Response> {
    const { pathname } = new URL(request.url);
    if (pathname === "/authorize" && request.method === "GET") {
      return authorizeGet(request, env);
    }
    if (pathname === "/authorize" && request.method === "POST") {
      return authorizePost(request, env);
    }
    if (pathname === "/callback" && request.method === "GET") {
      return callback(request, env);
    }
    if (pathname === "/" && request.method === "GET") {
      return Response.json({
        name: "Substack MCP",
        mcp_endpoint: "/mcp",
        authentication: "OAuth 2.1 via GitHub",
      });
    }
    return new Response("Not found", { status: 404 });
  },
};
