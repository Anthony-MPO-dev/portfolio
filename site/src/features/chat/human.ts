// The browser proof a new conversation needs (Cloudflare Turnstile, invisible): the API checks it once, when a
// conversation opens, so a script calling the API directly can't start one. Cloudflare's script loads only when the
// chat asks for a token, never with the page. No site key (a dev build) or no answer in 10 s gives no token: the API
// without a secret doesn't ask, and with one it answers "challenge", which the chat shows as a notice.
// Public API: humanToken. Used by: chat.tsx. Tests: none (Cloudflare's script; the API side is tested).

const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const SITEKEY = import.meta.env.VITE_TURNSTILE_SITEKEY as string | undefined;

type Turnstile = {
  render(box: HTMLElement, options: Record<string, unknown>): string;
  remove(id: string): void;
};
declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

let loading: Promise<void> | null = null;

function load(): Promise<void> {
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      loading = null; // try again on the next message
      reject(new Error("turnstile"));
    };
    document.head.append(script);
  });
  return loading;
}

export async function humanToken(timeoutMs = 10_000): Promise<string | undefined> {
  if (!SITEKEY) return undefined;
  try {
    await load();
  } catch {
    return undefined;
  }
  return new Promise((resolve) => {
    const box = document.createElement("div");
    document.body.append(box);
    let id = "";
    const done = (token?: string) => {
      clearTimeout(timer);
      if (id) window.turnstile?.remove(id);
      box.remove();
      resolve(token);
    };
    const timer = setTimeout(() => done(), timeoutMs);
    id =
      window.turnstile?.render(box, {
        sitekey: SITEKEY,
        callback: (token: string) => done(token),
        "error-callback": () => done(),
      }) ?? "";
  });
}
