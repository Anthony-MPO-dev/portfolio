// The browser proof a new conversation needs (Cloudflare Turnstile, managed mode).
// Responsibility: load Cloudflare's script only when the chat asks for a token (never with the page), render the
// widget in the box the chat gives it (inside the panel; with appearance "interaction-only" it shows only when
// Cloudflare wants a click, say from a VPN), and resolve the token, or nothing: no site key (a dev build), a failed
// load, an error, or no answer in 15 s (60 s once the visitor is asked to click). It never rejects, so the chat can't
// hang on it; without a token the API answers "challenge" and the chat shows what to do.
// Public API: humanToken, proofWith (the core, with its loader injected), Turnstile.
// Used by: chat.tsx. Depends on: Cloudflare's api.js (loaded on demand). Tests: human.test.ts.

const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export type Turnstile = {
  render(box: HTMLElement, options: Record<string, unknown>): string;
  remove(id: string): void;
};
declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

type Deps = { sitekey?: string; load: () => Promise<Turnstile>; wait?: number; waitForClick?: number };

export function proofWith({ sitekey, load, wait = 15_000, waitForClick = 60_000 }: Deps) {
  return (box: HTMLElement): Promise<string | undefined> =>
    new Promise((resolve) => {
      if (!sitekey) return resolve(undefined);
      let api: Turnstile | undefined;
      let id = "";
      let settled = false;
      const finish = (token?: string) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        try {
          if (id) api?.remove(id);
        } catch {
          // the widget is already gone
        }
        resolve(token);
      };
      let timer = setTimeout(() => finish(), wait);
      load()
        .then((loaded) => {
          if (settled) return;
          api = loaded;
          id = loaded.render(box, {
            sitekey,
            appearance: "interaction-only",
            callback: (token: string) => finish(token),
            "error-callback": () => finish(),
            "expired-callback": () => finish(),
            "before-interactive-callback": () => {
              clearTimeout(timer); // a person is being asked to click: give them time
              timer = setTimeout(() => finish(), waitForClick);
            },
          });
        })
        .catch(() => finish());
    });
}

let loading: Promise<Turnstile> | null = null;

function loadScript(): Promise<Turnstile> {
  loading ??= new Promise<Turnstile>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("turnstile")));
    script.onerror = () => {
      script.remove();
      loading = null; // the next conversation tries again
      reject(new Error("turnstile"));
    };
    document.head.append(script);
  });
  return loading;
}

export const humanToken = proofWith({
  sitekey: import.meta.env.VITE_TURNSTILE_SITEKEY as string | undefined,
  load: loadScript,
});
