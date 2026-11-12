// The search's results type themselves in, like the bot writing them, with very quiet key clicks made by the Web Audio
// API (a short burst of filtered noise, no audio file). Sound starts only after the visitor searched, has a switch,
// and the choice is remembered in the browser (per-visitor convenience; any storage error is ignored). With reduced
// motion the text shows at once, without sound.
// Public API: useTypewriter, getSound, setSound. Used by: fact-search.tsx. Tests: map.test.ts (typedLengths).
import { useEffect, useState } from "react";
import { typedLengths } from "./map";

const KEY = "fact-search-sound";
let soundOn: boolean | null = null;

export function getSound(): boolean {
  if (soundOn === null) {
    try {
      soundOn = localStorage.getItem(KEY) !== "off";
    } catch {
      soundOn = true;
    }
  }
  return soundOn;
}

export function setSound(on: boolean) {
  soundOn = on;
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    // a private window: the choice lasts until the page reloads
  }
}

let audio: AudioContext | null = null;
let noise: AudioBuffer | null = null;

function keyClick() {
  if (!getSound()) return;
  try {
    audio ??= new AudioContext();
    if (!noise) {
      const length = Math.floor(audio.sampleRate * 0.014);
      noise = audio.createBuffer(1, length, audio.sampleRate);
      const data = noise.getChannelData(0);
      for (let i = 0; i < length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / length) ** 4;
    }
    const source = audio.createBufferSource();
    source.buffer = noise;
    source.playbackRate.value = 0.8 + Math.random() * 0.5;
    const band = audio.createBiquadFilter();
    band.type = "bandpass";
    band.frequency.value = 1500 + Math.random() * 1500;
    band.Q.value = 0.8;
    const gain = audio.createGain();
    gain.gain.value = 0.035 + Math.random() * 0.025; // very quiet
    source.connect(band).connect(gain).connect(audio.destination);
    source.start();
  } catch {
    // no audio here: the text still types
  }
}

const reducedMotion = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

// How much of each text is typed: one text after the other, `cps` characters a second, a click every 55 to 100 ms.
export function useTypewriter(texts: string[], key: string, cps = 220): number[] {
  const total = texts.reduce((s, t) => s + t.length, 0);
  const [n, setN] = useState(total);
  useEffect(() => {
    if (reducedMotion()) return setN(total);
    setN(0);
    let raf = 0;
    let start = 0;
    let last = 0;
    const tick = (t: number) => {
      start ||= t;
      const c = Math.min(total, Math.floor(((t - start) / 1000) * cps));
      setN(c);
      if (c >= total) return;
      if (t - last > 55 + Math.random() * 45) {
        keyClick();
        last = t;
      }
      raf = requestAnimationFrame(tick);
    };
    const wait = setTimeout(() => (raf = requestAnimationFrame(tick)), 350);
    return () => {
      clearTimeout(wait);
      cancelAnimationFrame(raf);
    };
    // a new search (key) restarts the typing
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return typedLengths(texts, n);
}
