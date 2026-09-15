import assert from "node:assert/strict";
import test from "node:test";
import { authHandler } from "./oauth.ts";

const base = "https://substack-mcp.example.com";
const invoke = (request: Request) => authHandler.fetch!(request, {} as never, {} as ExecutionContext);

test("diagnostic page sets only short-lived, secure non-authentication markers", async () => {
  const response = await invoke(new Request(`${base}/auth/diagnostics`));
  assert.equal(response.status, 200);
  const cookies = response.headers.getSetCookie();
  assert.equal(cookies.length, 2);
  for (const cookie of cookies) {
    assert.match(cookie, /^(?:__Host-)?SUBSTACK_MCP_DIAGNOSTIC=1;/);
    for (const flag of ["HttpOnly", "Secure", "Path=/", "SameSite=Lax", "Max-Age=120"]) {
      assert.ok(cookie.includes(flag));
    }
    assert.ok(!cookie.includes("Domain="));
  }
  assert.match(response.headers.get("Cache-Control") ?? "", /no-store/);
  assert.match(response.headers.get("Content-Security-Policy") ?? "", /frame-ancestors 'none'/);
  const html = await response.text();
  assert.match(html, /method="post" action="\/auth\/diagnostics\/check"/);
  assert.match(html, /href="\/auth\/diagnostics\/check"/);
});

test("diagnostic GET and POST distinguish marker delivery without revealing cookie data", async () => {
  for (const method of ["GET", "POST"]) {
    for (const [cookie, expected] of [
      ["", [false, false]],
      ["SUBSTACK_MCP_DIAGNOSTIC=1; unrelated=private-secret", [false, true]],
      ["__Host-SUBSTACK_MCP_DIAGNOSTIC=1; SUBSTACK_MCP_DIAGNOSTIC=1", [true, true]],
    ] as const) {
      const response = await invoke(new Request(`${base}/auth/diagnostics/check`, {
        method, headers: { Cookie: cookie, Accept: "application/json", Origin: "https://private.example" },
      }));
      assert.equal(response.status, 200);
      assert.match(response.headers.get("Cache-Control") ?? "", /no-store/);
      const data = await response.json();
      assert.deepEqual(data, { method, host_cookie_received: expected[0], plain_cookie_received: expected[1] });
      assert.ok(!JSON.stringify(data).includes("private"));
      assert.equal(response.headers.get("Access-Control-Allow-Origin"), null);
      assert.equal(response.headers.get("Location"), null);
    }
  }
});

test("diagnostic HTML uses fixed labels and rejects unrelated methods", async () => {
  const response = await invoke(new Request(`${base}/auth/diagnostics/check`, {
    method: "POST", headers: { Accept: "text/html", Cookie: "SUBSTACK_MCP_DIAGNOSTIC=secret-value" },
  }));
  const html = await response.text();
  assert.match(html, /POST/);
  assert.match(html, /未到達/);
  assert.ok(!html.includes("secret-value"));
  const denied = await invoke(new Request(`${base}/auth/diagnostics/check`, { method: "PUT" }));
  assert.equal(denied.status, 404);
});
