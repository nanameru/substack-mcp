import { env as cloudflareEnv } from "cloudflare:workers";
import { Container } from "@cloudflare/containers";
import { OAuthProvider } from "@cloudflare/workers-oauth-provider";
import { McpServer } from "@modelcontextprotocol/server";
import { createMcpHandler, getMcpAuthContext } from "agents/mcp/server";
import { z } from "zod";

import { authHandler } from "./oauth";
import type { Env } from "./types";

const env = cloudflareEnv as unknown as Env;

export class SubstackContainer extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "10m";
  pingEndpoint = "/ping";
  enableInternet = true;

  constructor(ctx: DurableObjectState<{}>, workerEnv: Env) {
    super(ctx, workerEnv);
    this.envVars = {
      SUBSTACK_PUBLICATION_URL: workerEnv.SUBSTACK_PUBLICATION_URL,
      SUBSTACK_SESSION_TOKEN: workerEnv.SUBSTACK_SESSION_TOKEN,
    };
  }
}

function allowedLogins(): string[] {
  return env.ALLOWED_GITHUB_LOGINS.split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function assertAuthorized(): void {
  const login = getMcpAuthContext()?.props?.login;
  if (typeof login !== "string" || !allowedLogins().includes(login.toLowerCase())) {
    throw new Error("This GitHub identity is not authorized for Substack tools");
  }
}

async function invoke(tool: string, arguments_: Record<string, unknown>) {
  assertAuthorized();
  const container = env.SUBSTACK_CONTAINER.getByName("primary");
  const response = await container.fetch("http://container/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool, arguments: arguments_ }),
  });
  const payload = (await response.json()) as { result?: unknown; error?: string };
  if (!response.ok || !("result" in payload)) {
    throw new Error(payload.error || `Substack backend returned HTTP ${response.status}`);
  }
  return payload.result;
}

function result(value: unknown) {
  const structuredContent =
    value !== null && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : { items: value };
  return {
    content: [{ type: "text" as const, text: JSON.stringify(value, null, 2) }],
    structuredContent,
  };
}

function createServer() {
  const server = new McpServer({ name: "Substack MCP", version: "0.2.0" });

  server.registerTool(
    "create_draft",
    {
      title: "Create Substack draft",
      description: "Create a private Substack article draft from Markdown. This does not publish or email it.",
      inputSchema: {
        title: z.string().min(1).max(280).describe("Article title"),
        content_markdown: z.string().min(1).describe("Full article body in Markdown"),
        subtitle: z.string().max(280).default("").describe("Optional subtitle"),
        audience: z.enum(["everyone", "only_paid", "founding", "only_free"]).default("everyone"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: true },
    },
    async (args) => result(await invoke("create_draft", args)),
  );

  server.registerTool(
    "update_draft",
    {
      title: "Update Substack draft",
      description: "Update selected fields of an existing Substack draft. Omitted fields are unchanged.",
      inputSchema: {
        post_id: z.string().min(1),
        title: z.string().min(1).max(280).optional(),
        subtitle: z.string().max(280).optional(),
        content_markdown: z.string().min(1).optional(),
        audience: z.enum(["everyone", "only_paid", "founding", "only_free"]).optional(),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: true },
    },
    async (args) => result(await invoke("update_draft", args)),
  );

  server.registerTool(
    "upload_image",
    {
      title: "Upload image to Substack",
      description: "Upload an image from a public HTTPS URL to the Substack CDN and return its CDN URL.",
      inputSchema: {
        image_url: z.url().refine((url) => url.startsWith("https://"), "Use a public HTTPS URL"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: true },
    },
    async (args) => result(await invoke("upload_image", args)),
  );

  server.registerTool(
    "set_cover_image",
    {
      title: "Set draft cover image",
      description: "Set a public image URL as the cover thumbnail of an existing Substack draft.",
      inputSchema: { post_id: z.string().min(1), image_url: z.url() },
      annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: true },
    },
    async (args) => result(await invoke("set_cover_image", args)),
  );

  server.registerTool(
    "publish_draft",
    {
      title: "Publish Substack draft",
      description: "Publish a draft immediately. This can send an irreversible email to subscribers; call only after explicit user confirmation.",
      inputSchema: {
        post_id: z.string().min(1),
        send_email: z.boolean().default(false).describe("Send the published post to subscribers by email"),
        share_automatically: z.boolean().default(false),
      },
      annotations: { readOnlyHint: false, destructiveHint: true, openWorldHint: true },
    },
    async (args) => result(await invoke("publish_draft", args)),
  );

  server.registerTool(
    "schedule_draft",
    {
      title: "Schedule Substack draft",
      description: "Schedule an existing draft for future publication at an ISO 8601 date and time.",
      inputSchema: {
        post_id: z.string().min(1),
        iso_datetime: z.iso.datetime({ offset: true }).describe("For example 2026-09-15T09:00:00+09:00"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: true },
    },
    async (args) => result(await invoke("schedule_draft", args)),
  );

  server.registerTool(
    "unschedule_draft",
    {
      title: "Cancel scheduled publication",
      description: "Cancel scheduled publication and keep the post as a draft.",
      inputSchema: { post_id: z.string().min(1) },
      annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: true },
    },
    async (args) => result(await invoke("unschedule_draft", args)),
  );

  server.registerTool(
    "list_drafts",
    {
      title: "List Substack drafts",
      description: "List recent unpublished drafts in the authenticated Substack publication.",
      inputSchema: { limit: z.number().int().min(1).max(50).default(10) },
      annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    },
    async (args) => result(await invoke("list_drafts", args)),
  );

  server.registerTool(
    "get_draft",
    {
      title: "Get Substack draft",
      description: "Get one draft including its body content.",
      inputSchema: { post_id: z.string().min(1) },
      annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    },
    async (args) => result(await invoke("get_draft", args)),
  );

  server.registerTool(
    "delete_draft",
    {
      title: "Delete Substack draft",
      description: "Permanently delete a Substack draft. This cannot be undone; call only after explicit user confirmation.",
      inputSchema: { post_id: z.string().min(1) },
      annotations: { readOnlyHint: false, destructiveHint: true, openWorldHint: false },
    },
    async (args) => result(await invoke("delete_draft", args)),
  );

  server.registerTool(
    "post_note",
    {
      title: "Publish Substack Note",
      description: "Immediately publish a short Note to the public Substack feed. Call only after explicit user confirmation.",
      inputSchema: { text: z.string().min(1).max(4000) },
      annotations: { readOnlyHint: false, destructiveHint: true, openWorldHint: true },
    },
    async (args) => result(await invoke("post_note", args)),
  );

  return server;
}

const apiHandler = createMcpHandler(createServer);

export default new OAuthProvider({
  authorizeEndpoint: "/authorize",
  tokenEndpoint: "/oauth/token",
  clientRegistrationEndpoint: "/oauth/register",
  apiRoute: "/mcp",
  apiHandler: apiHandler as any,
  defaultHandler: authHandler,
});
