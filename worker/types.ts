import type { SubstackContainer } from "./index";

export interface Env {
  SUBSTACK_CONTAINER: DurableObjectNamespace<SubstackContainer>;
  OAUTH_KV: KVNamespace;
  SUBSTACK_PUBLICATION_URL: string;
  SUBSTACK_SESSION_TOKEN: string;
  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  ALLOWED_GITHUB_LOGINS: string;
}
