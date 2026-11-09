// The site's Content-Security-Policy, written at build time: scripts run only from this site, from Cloudflare's
// analytics beacon, or when their exact text is one of the inline scripts the prerender wrote (hashed here), so an
// injected <script> never runs. Run after the build: node scripts/csp.mjs build/client > build/csp.conf; nginx
// includes that file. Styles keep 'unsafe-inline' (React's style attributes).
// Public API: inlineScriptHashes, cspHeader. Tests: csp.test.mjs.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const RUNS_AS_CODE = /^(module|text\/javascript)$/;

export function inlineScriptHashes(html) {
  return [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)]
    .filter(([, attrs]) => {
      const type = /\btype="([^"]*)"/.exec(attrs)?.[1];
      return !/\bsrc=/.test(attrs) && (!type || RUNS_AS_CODE.test(type));
    })
    .map(([, , text]) => `'sha256-${createHash("sha256").update(text, "utf8").digest("base64")}'`);
}

export function cspHeader(hashes) {
  const policy = [
    "default-src 'self'",
    `script-src 'self' ${hashes.join(" ")} https://static.cloudflareinsights.com`,
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self'",
    // images and requests only from this site: a chat reply can't leak anything through an image URL
    "img-src 'self' data:",
    "connect-src 'self' https://cloudflareinsights.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
  return `add_header Content-Security-Policy "${policy}" always;\n`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dir = process.argv[2];
  const pages = readdirSync(dir, { recursive: true }).filter((f) => String(f).endsWith(".html"));
  const hashes = new Set(pages.flatMap((f) => inlineScriptHashes(readFileSync(join(dir, String(f)), "utf8"))));
  if (!hashes.size) throw new Error(`no inline scripts found in ${dir}: is the build there?`);
  process.stdout.write(cspHeader([...hashes].sort()));
}
