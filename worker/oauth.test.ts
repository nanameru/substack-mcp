import assert from "node:assert/strict";
import test from "node:test";

import { authHandler } from "./oauth.ts";

const BASE_URL = "https://substack-mcp.example.com";

class FakeKv {
  values = new Map<string, string>();

  async put(key: string, value: string) {
    this.values.set(key, value);
  }

  async get(key: string) {
    return this.values.get(key) ?? null;
  }

  async delete(key: string) {
    this.values.delete(key);
  }
}

function hiddenValue(html: string, name: string): string {
  const match = html.match(new RegExp(`name="${name}" value="([^"]+)"`));
  assert.ok(match, `missing hidden input ${name}`);
  return match[1];
}

function updateCookieJar(jar: Map<string, string>, setCookie: string | null): void {
  assert.ok(setCookie, "missing Set-Cookie header");
  const [pair] = setCookie.split(";", 1);
  const separator = pair.indexOf("=");
  const name = pair.slice(0, separator);
  const value = pair.slice(separator + 1);
  if (setCookie.includes("Max-Age=0")) jar.delete(name);
  else jar.set(name, value);
}

function cookieHeader(jar: Map<string, string>): string {
  return [...jar].map(([name, value]) => `${name}=${value}`).join("; ");
}

test("keeps concurrent authorization forms valid in the same browser", async () => {
  const kv = new FakeKv();
  const authRequest = {
    clientId: "chatgpt-client",
    redirectUri: "https://chatgpt.com/connector/oauth/callback",
    responseType: "code",
    scope: [],
  };
  const env = {
    OAUTH_KV: kv,
    OAUTH_PROVIDER: {
      async parseAuthRequest() {
        return authRequest;
      },
      async lookupClient() {
        return { clientName: "ChatGPT" };
      },
    },
    GITHUB_CLIENT_ID: "test-client-id",
  };
  const cookies = new Map<string, string>();

  const firstGet = await authHandler.fetch!(
    new Request(`${BASE_URL}/authorize`),
    env as never,
    {} as ExecutionContext,
  );
  const firstHtml = await firstGet.text();
  const firstCsrf = hiddenValue(firstHtml, "csrf_token");
  const firstState = hiddenValue(firstHtml, "state");
  updateCookieJar(cookies, firstGet.headers.get("Set-Cookie"));

  const secondGet = await authHandler.fetch!(
    new Request(`${BASE_URL}/authorize`),
    env as never,
    {} as ExecutionContext,
  );
  const secondHtml = await secondGet.text();
  const secondCsrf = hiddenValue(secondHtml, "csrf_token");
  const secondState = hiddenValue(secondHtml, "state");
  updateCookieJar(cookies, secondGet.headers.get("Set-Cookie"));

  const submit = async (csrfToken: string, state: string) =>
    authHandler.fetch!(
      new Request(`${BASE_URL}/authorize`, {
        method: "POST",
        headers: {
          Cookie: cookieHeader(cookies),
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({ csrf_token: csrfToken, state }),
      }),
      env as never,
      {} as ExecutionContext,
    );

  const firstPost = await submit(firstCsrf, firstState);
  assert.equal(firstPost.status, 302);
  assert.match(firstPost.headers.get("Location") ?? "", /^https:\/\/github\.com\/login\/oauth\/authorize/);
  for (const cookie of firstPost.headers.getSetCookie()) updateCookieJar(cookies, cookie);

  const secondPost = await submit(secondCsrf, secondState);
  assert.equal(secondPost.status, 302);
  assert.match(secondPost.headers.get("Location") ?? "", /^https:\/\/github\.com\/login\/oauth\/authorize/);
});

test("authorization pages cannot be cached", async () => {
  const response = await authHandler.fetch!(new Request(`${BASE_URL}/authorize`), {
    OAUTH_PROVIDER: {
      async parseAuthRequest() { return { clientId: "test", redirectUri: "https://chatgpt.com/connector/oauth/callback" }; },
      async lookupClient() { return { clientName: "ChatGPT" }; },
    },
  } as never, {} as ExecutionContext);
  assert.match(response.headers.get("Cache-Control") ?? "", /no-store/);
});

test("permits the validated OAuth callback origin in the form redirect chain", async () => {
  const response = await authHandler.fetch!(new Request(`${BASE_URL}/authorize`), {
    OAUTH_PROVIDER: {
      async parseAuthRequest() {
        return { clientId: "test", redirectUri: "https://chatgpt.com/connector/oauth/callback?private=hidden" };
      },
      async lookupClient() { return { clientName: "ChatGPT" }; },
    },
  } as never, {} as ExecutionContext);
  const policy = response.headers.get("Content-Security-Policy") ?? "";
  const formAction = policy.split(";").find((part) => part.trim().startsWith("form-action"));
  assert.ok(formAction?.split(/\s+/).includes("https://chatgpt.com"));
  assert.ok(!policy.includes("private"));
  assert.match(policy, /default-src 'none'/);
  assert.match(policy, /frame-ancestors 'none'/);
});

test("does not allow callback paths to inject CSP directives", async () => {
  const response = await authHandler.fetch!(new Request(`${BASE_URL}/authorize`), {
    OAUTH_PROVIDER: {
      async parseAuthRequest() {
        return { clientId: "test", redirectUri: "https://chatgpt.com/;script-src *" };
      },
      async lookupClient() { return { clientName: "ChatGPT" }; },
    },
  } as never, {} as ExecutionContext);
  assert.ok(!(response.headers.get("Content-Security-Policy") ?? "").includes("script-src"));
});

for (const scenario of [
  { name: "missing form", token: null, cookie: "", code: "CSRF_FORM_MISSING" },
  { name: "missing cookie", token: "diagnostic-token", cookie: "", code: "CSRF_COOKIE_MISSING" },
  { name: "mismatch", token: "diagnostic-token", cookie: "__Host-SUBSTACK_MCP_CSRF_diagnostictoken=wrong-secret-value", code: "CSRF_TOKEN_MISMATCH" },
]) {
  test(`rejects ${scenario.name} with a safe diagnostic and no side effects`, async () => {
    const kv = new FakeKv();
    const form = new URLSearchParams({ state: "private-state" });
    if (scenario.token) form.set("csrf_token", scenario.token);
    for (const accept of ["application/json", "text/html"]) {
      const response = await authHandler.fetch!(new Request(`${BASE_URL}/authorize`, {
        method: "POST", headers: { Cookie: scenario.cookie, Accept: accept }, body: form,
      }), { OAUTH_KV: kv } as never, {} as ExecutionContext);
      assert.equal(response.status, 400);
      assert.match(response.headers.get("Cache-Control") ?? "", /no-store/);
      const body = await response.text();
      assert.ok(body.includes(scenario.code));
      for (const secret of ["diagnostic-token", "wrong-secret-value", "private-state"]) {
        assert.ok(!body.includes(secret));
      }
      assert.equal(response.headers.get("Location"), null);
      assert.equal(kv.values.size, 0);
    }
  });
}
