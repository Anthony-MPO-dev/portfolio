import { lazy, Suspense, type ReactNode } from "react";
import { Links, Meta, Outlet, Scripts, ScrollRestoration } from "react-router";
// Fonts are served from the site (hashed, immutable assets), with swap: no third-party request before the text shows.
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/ibm-plex-mono/500.css";
import archivoLatin from "@fontsource-variable/archivo/files/archivo-latin-wdth-normal.woff2?url";
import "@/styles/global.css";

// HTML shell of every prerendered page: fonts, and the boot script that applies the saved theme before paint.

// Runs before paint so the saved theme applies without a flash.
const bootScript = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export function links() {
  return [
    // the headline font, fetched with the HTML instead of after the CSS
    { rel: "preload", href: archivoLatin, as: "font", type: "font/woff2", crossOrigin: "anonymous" },
    // no icon yet (the author picks one): an empty one stops the browser's request for /favicon.ico and its 404
    { rel: "icon", href: "data:," },
  ];
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <script dangerouslySetInnerHTML={{ __html: bootScript }} />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

// The chat stays out of the page until its security work is done: only a build with VITE_CHAT=1 includes it, and
// then it loads after the page.
const Chat =
  import.meta.env.VITE_CHAT === "1" ? lazy(() => import("@/features/chat/chat").then((m) => ({ default: m.Chat }))) : null;

export default function App() {
  return (
    <>
      <Outlet />
      {Chat && (
        <Suspense fallback={null}>
          <Chat lang="en" />
        </Suspense>
      )}
    </>
  );
}
