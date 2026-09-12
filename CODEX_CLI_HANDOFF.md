# Codex CLI handoff: deploy Substack MCP to Cloudflare

## Goal

Deploy this repository as a private Remote MCP on Cloudflare so ChatGPT can
operate Substack without an always-on computer. ChatGPT performs all writing
and reasoning. Cloudflare only hosts the authenticated MCP tools and the
on-demand Python backend.

Do not request or configure an OpenAI API key. Do not use OpenAI Secure MCP
Tunnel. Do not publish a Substack post or Note during deployment validation.

## Current state

- PR #3 added the optional local Secure MCP Tunnel flow.
- PR #4 added the Cloudflare implementation and was merged into `main`.
- `worker/index.ts` exposes a stateless Streamable HTTP MCP at `/mcp`.
- `worker/oauth.ts` implements OAuth 2.1 using GitHub login and an allowlist.
- `SubstackContainer` starts the existing Python client only when requested.
- `src/substack_mcp/cloud_api.py` is the private Worker-to-Container bridge.
- The Worker bundle, Python syntax, TypeScript types, and bridge dispatch were
  validated before handoff.

## Security requirements

- Never print, echo, log, commit, or paste `substack.sid` into an AI chat.
- Store credentials only with `wrangler secret put` or its secure stdin input.
- Restrict `ALLOWED_GITHUB_LOGINS` to the owner's GitHub login (`nanameru` unless
  the user explicitly chooses another account).
- Do not weaken OAuth or expose the Python Container directly.
- Do not call `publish_draft`, `delete_draft`, or `post_note` while testing.
- Keep `publish_draft.send_email` defaulted to `false`.

## Continue in Codex CLI

1. Confirm the checkout is clean and current:

   ```bash
   git switch main
   git pull --ff-only
   npm install
   npm run type-check
   ```

2. Authenticate Cloudflare interactively. The browser may be closed after the
   deployment finishes:

   ```bash
   npx wrangler login
   npx wrangler whoami
   ```

3. Confirm Workers Containers are enabled for the selected Cloudflare account.
   If the account or plan does not support Containers, stop and report the exact
   Cloudflare error instead of changing the architecture silently.

4. Create the OAuth KV namespace:

   ```bash
   npx wrangler kv namespace create OAUTH_KV
   ```

   Replace `REPLACE_WITH_OAUTH_KV_ID` in `wrangler.jsonc` with the returned ID.
   Never substitute a guessed ID.

5. Determine the final Worker hostname, normally:

   ```text
   https://substack-mcp.<workers-subdomain>.workers.dev
   ```

6. Ask the user to create one GitHub OAuth App at
   `https://github.com/settings/developers` with:

   - Homepage URL: the Worker URL above
   - Authorization callback URL: `<Worker URL>/callback`

   Ask the user to enter the resulting Client ID and Client secret only into
   Wrangler's terminal prompts:

   ```bash
   npx wrangler secret put GITHUB_CLIENT_ID
   npx wrangler secret put GITHUB_CLIENT_SECRET
   npx wrangler secret put ALLOWED_GITHUB_LOGINS
   npx wrangler secret put SUBSTACK_PUBLICATION_URL
   npx wrangler secret put SUBSTACK_SESSION_TOKEN
   ```

   Set `ALLOWED_GITHUB_LOGINS` to `nanameru` unless the user says otherwise.
   The Substack publication URL is the full publication origin.

7. If the user already ran `substack-mcp-setup`, the macOS credential file is:

   ```text
   ~/Library/Application Support/substack-mcp/config.json
   ```

   The session token may be piped from that file directly into
   `wrangler secret put SUBSTACK_SESSION_TOKEN`, but it must never be displayed.
   If the file does not exist, run `substack-mcp-setup` while the user is logged
   into Substack in Chrome, then retry. The browser is only needed for this
   one-time credential capture.

8. Deploy:

   ```bash
   npm run deploy
   ```

9. Validate without writing to Substack:

   - `GET <Worker URL>/` returns the Substack MCP information response.
   - `/mcp` requires OAuth and is not anonymously callable.
   - Complete GitHub OAuth with the allowlisted account.
   - List tools and invoke only `list_drafts(limit=1)` for the first live test.
   - Confirm the following tools exist: `create_draft`, `update_draft`,
     `upload_image`, `set_cover_image`, `publish_draft`, `schedule_draft`,
     `unschedule_draft`, `list_drafts`, `get_draft`, `delete_draft`, `post_note`.

10. Give the user the final MCP URL:

    ```text
    <Worker URL>/mcp
    ```

    They can add this URL as a custom ChatGPT app/connector and choose OAuth.

## Completion criteria

- Deployment succeeds on Cloudflare Workers + Containers.
- OAuth rejects GitHub users outside the allowlist.
- ChatGPT can connect to the public HTTPS `/mcp` endpoint.
- `list_drafts(limit=1)` succeeds without modifying Substack.
- The computer can be turned off and the MCP remains callable.

Substack has no public posting API. This project uses a browser session cookie
and Substack's internal API, so signing out of all Substack sessions or an
upstream API change may require refreshing the Cloudflare secret later.
