// One-time diagnostic. Never print the token or the complete claim set.
const token = process.env.ACTIONS_RUNTIME_TOKEN;
if (!token) throw new Error("Cache runtime token is unavailable");
const claims = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString());
const access = typeof claims.ac === "string" ? JSON.parse(claims.ac) : claims.ac;
if (!Array.isArray(access)) throw new Error("Cache grants are unavailable");
const scopes = access.map(({ Scope, Permission }) => {
  if (typeof Scope !== "string" || !Scope.startsWith("refs/") ||
      typeof Permission !== "number") {
    throw new Error("Unexpected cache grant shape");
  }
  return { ref: Scope, permission: Permission };
});
console.log("[DEBUG-spa-cache-scope] " + JSON.stringify({
  event: process.env.GITHUB_EVENT_NAME,
  ref: process.env.GITHUB_REF,
  head: process.env.GITHUB_HEAD_REF,
  base: process.env.GITHUB_BASE_REF,
  scopes,
}));
