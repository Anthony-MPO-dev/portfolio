import { useRef } from "react";
import { cases, profile } from "@/content/profile";
import { useReveal } from "@/hooks/use-reveal";
import { step } from "@/lib/step";
import "./schematic.css";

// PROTOTYPE direction A: an engineering drawing. The credit pipeline draws itself while the scene is pinned.
const BUREAUS = [0, 1, 2, 3, 4];
const WORKERS = [80, 200, 320];

export function Schematic() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);

  return (
    <main className="va" ref={root}>
      <header className="va-top">
        <span>anthonymuniz.dev</span>
        <span>Open to remote roles</span>
      </header>

      <section className="va-hero">
        <p className="va-label">
          {profile.name} / {profile.role}
        </p>
        <h1>{profile.headline}</h1>
        <p className="va-lede">{profile.lede}</p>
      </section>

      <section className="va-scene scene" aria-label="Credit pipeline">
        <div className="va-sticky">
          <div className="va-caption">
            <p className="va-label">Fig. 1, credit analysis pipeline</p>
            <p>
              Five credit bureaus in, one report out. A credit analysis took about an hour, and this pipeline gets it done
              in as little as 5 minutes. Moving the heavy work to RabbitMQ and Celery workers took capacity from about 10
              to up to 100 operations a day.
            </p>
          </div>
          <svg
            className="va-svg"
            viewBox="0 0 400 600"
            role="img"
            aria-label="Five credit bureaus feed a RabbitMQ queue, three workers run the analysis and a report comes out. The time drops from about an hour to as little as 5 minutes."
          >
            <text x="200" y="14" textAnchor="middle" className="va-small">
              5+ credit bureaus
            </text>
            {BUREAUS.map((b) => {
              const x = 10 + b * 78;
              return (
                <g key={b}>
                  <rect x={x} y={26} width={66} height={40} pathLength={1} className="draw" style={step(0)} />
                  <text x={x + 33} y={51} textAnchor="middle" className="va-node fade-in" style={step(1)}>
                    B{b + 1}
                  </text>
                  <path
                    d={`M${x + 33} 66 C ${x + 33} 130, 200 120, 200 186`}
                    pathLength={1}
                    className="draw va-wire"
                    style={step(1)}
                  />
                </g>
              );
            })}
            <rect x={110} y={186} width={180} height={56} pathLength={1} className="draw" style={step(2)} />
            <text x={200} y={219} textAnchor="middle" className="va-node fade-in" style={step(3)}>
              RabbitMQ queue
            </text>
            {WORKERS.map((cx) => (
              <g key={cx}>
                <path d={`M200 242 C 200 280, ${cx} 270, ${cx} 316`} pathLength={1} className="draw va-wire" style={step(3)} />
                <rect x={cx - 55} y={316} width={110} height={48} pathLength={1} className="draw" style={step(4)} />
                <text x={cx} y={345} textAnchor="middle" className="va-node fade-in" style={step(5)}>
                  worker
                </text>
                <path d={`M${cx} 364 C ${cx} 410, 200 400, 200 446`} pathLength={1} className="draw va-wire" style={step(5)} />
              </g>
            ))}
            <rect x={120} y={446} width={160} height={56} pathLength={1} className="draw va-accent" style={step(6)} />
            <text x={200} y={479} textAnchor="middle" className="va-node fade-in" style={step(7)}>
              report
            </text>
            <text x={200} y={570} textAnchor="middle" className="va-time fade-out" style={step(7)}>
              about 1 hour
            </text>
            <text x={200} y={570} textAnchor="middle" className="va-time va-time-new fade-in" style={step(8)}>
              down to 5 min
            </text>
          </svg>
        </div>
      </section>

      <section className="va-index">
        <h2 className="va-label">Selected work</h2>
        <ol>
          {cases.map((c, n) => (
            <li key={c.id} className="reveal">
              <span className="va-num">{String(n + 1).padStart(2, "0")}</span>
              <div>
                <h3>{c.title}</h3>
                <p>{c.summary}</p>
              </div>
              <ul className="va-figs">
                {c.numbers.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              <p className="va-stack">
                {c.when}. {c.stack}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section className="va-contact">
        <h2>Have a system that should work better? Write to me.</h2>
        <a className="va-mail" href={`mailto:${profile.email}`}>
          {profile.email}
        </a>
        <p className="va-links">
          <a href={profile.linkedin}>LinkedIn</a>
          <a href={profile.github}>GitHub</a>
        </p>
        <p className="va-open">{profile.open}</p>
      </section>
    </main>
  );
}
