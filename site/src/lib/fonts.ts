// The opening waits for its font. The headline is Archivo at 72% width; the fallback font is far wider, so text
// painted before Archivo arrives wraps onto more lines and the whole opening jumps when it swaps in (real visitors:
// CLS 0.35 on desktop, 2026-11-17). FONT_BOOT runs before paint and marks the page .fonts-wait until the fonts are
// ready, at most FONT_WAIT_MS; the CSS keeps the opening hidden and its animations paused meanwhile, so the headline
// types itself in Archivo and nothing moves. Without the font loading API (or without JS) the opening shows at once.
// Public API: FONT_BOOT, FONT_WAIT_MS.
// Used by: app/root.tsx (the boot script); app/routes/home-entrance.css reads .fonts-wait.
// Tests: fonts.test.ts.

// Long enough for a preloaded 90 KB font on a slow line, short enough that the opening isn't blank for long.
export const FONT_WAIT_MS = 1200;

export const FONT_BOOT = `try{var f=document.fonts,c=document.documentElement.classList;if(f){c.add("fonts-wait");var go=function(){c.remove("fonts-wait")};f.ready.then(go,go);setTimeout(go,${FONT_WAIT_MS})}}catch(e){}`;
