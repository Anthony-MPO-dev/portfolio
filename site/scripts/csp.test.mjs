import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { cspHeader, inlineScriptHashes } from "./csp.mjs";

const sha = (text) => `'sha256-${createHash("sha256").update(text, "utf8").digest("base64")}'`;

describe("inlineScriptHashes", () => {
  it("hashes the exact text of each inline script, modules included", () => {
    const html = `<script>a()</script><script type="module" async="">import "/x.js";\n</script>`;
    expect(inlineScriptHashes(html)).toEqual([sha("a()"), sha('import "/x.js";\n')]);
  });

  it("skips external scripts and JSON data blocks, which never run as code", () => {
    const html = `<script src="/a.js"></script><script type="application/ld+json">{"a":1}</script><script>b()</script>`;
    expect(inlineScriptHashes(html)).toEqual([sha("b()")]);
  });
});

describe("cspHeader", () => {
  const header = cspHeader(["'sha256-x'", "'sha256-y'"]);

  it("lets scripts run only from this site, the listed hashes, Cloudflare's analytics beacon and Turnstile", () => {
    expect(header).toContain(
      "script-src 'self' 'sha256-x' 'sha256-y' https://static.cloudflareinsights.com https://challenges.cloudflare.com;",
    );
    expect(header).toContain("frame-src https://challenges.cloudflare.com;");
    expect(header).not.toMatch(/script-src[^;]*'unsafe-inline'/);
  });

  it("is an nginx line that also applies to error responses", () => {
    expect(header).toMatch(/^add_header Content-Security-Policy ".+" always;\n$/);
  });
});
