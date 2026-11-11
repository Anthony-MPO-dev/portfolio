import type { CSSProperties } from "react";
import { offer } from "@/content/services";
import { step } from "@/lib/step";

// The four services, each with a small drawing of its before turning into its after (the before fades, the after
// draws in), played once when the row comes into view ([data-reveal], useReveal). The drawings repeat figures the
// text already gives, so they are hidden from screen readers.
// Public API: Offer. Used by app/routes/services.tsx.

export function Offer() {
  return (
    <section className="svc-offer" aria-label="Services">
      <p className="svc-kicker">{offer.kicker}</p>
      {offer.services.map((s) => (
        <article key={s.id} className="svc-row" data-reveal>
          <Turn id={s.id} />
          <div>
            <h2>{s.name}</h2>
            <p>{s.line}</p>
            <p className="svc-proof">{s.proof}</p>
          </div>
        </article>
      ))}
    </section>
  );
}

const DOTS = [
  [10, 50],
  [40, 30],
  [62, 58],
  [90, 40],
  [120, 20],
  [150, 44],
  [190, 14],
  [240, 30],
];

function Turn({ id }: { id: string }) {
  return (
    <svg className="svc-turn" viewBox="0 0 260 90" aria-hidden="true">
      {id === "automation" && (
        <>
          {["copy", "paste", "check", "email", "file"].map((w, k) => (
            <text
              key={w}
              x={6 + k * 50}
              y={22}
              className="fade-out"
              style={{ ...step(k), "--swap-y": "0px" } as CSSProperties}
            >
              {w}
            </text>
          ))}
          <path d="M6 60 H248" pathLength={1} className="draw svc-line" style={step(5)} />
          <path d="M240 52 L250 60 L240 68" pathLength={1} className="draw svc-line" style={step(6)} />
          <text x={6} y={86} className="fade-in" style={step(7)}>
            1 hour → as fast as 5 min
          </text>
        </>
      )}
      {id === "agents" && (
        <>
          {["question", "your docs", "answer", "a person"].map((w, k) => (
            <g key={w}>
              <rect
                x={4 + k * 64}
                y={12}
                width={58}
                height={26}
                rx={3}
                pathLength={1}
                className="draw"
                style={step(k * 2)}
              />
              <text x={33 + k * 64} y={29} textAnchor="middle" className="fade-in" style={step(k * 2 + 1)}>
                {w}
              </text>
            </g>
          ))}
          <path d="M225 38 V58 H33" pathLength={1} className="draw svc-line" style={step(8)} />
          <text x={6} y={86} className="fade-in" style={step(9)}>
            replies 3x faster, 45 s → 15 s
          </text>
        </>
      )}
      {id === "data" && (
        <>
          {DOTS.map(([x, y], k) => (
            <circle key={k} cx={x} cy={y} r={4} className="fade-in" style={step(k * 0.5)} />
          ))}
          <path
            d="M10 64 L40 58 L62 54 L90 46 L120 40 L150 32 L190 24 L240 14"
            pathLength={1}
            className="draw svc-line"
            style={step(5)}
          />
          <text x={6} y={86} className="fade-in" style={step(7)}>
            scattered numbers → one dashboard
          </text>
        </>
      )}
      {id === "software" && (
        <>
          {Array.from({ length: 10 }, (_, k) => (
            <rect
              key={k}
              x={6 + k * 25}
              y={10}
              width={21}
              height={56}
              rx={2}
              className={k === 0 ? "svc-cap" : "svc-cap grow"}
              style={step(k * 0.6)}
            />
          ))}
          <text x={6} y={86} className="fade-in" style={step(7)}>
            about 10 → as many as 100 operations a day
          </text>
        </>
      )}
    </svg>
  );
}
