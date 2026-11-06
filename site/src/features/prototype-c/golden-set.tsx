import { useRef } from "react";
import { cases, profile } from "@/content/profile";
import { useReveal } from "@/hooks/use-reveal";
import { step } from "@/lib/step";
import "./golden-set.css";

// PROTOTYPE direction C: editorial, numbers as the visual. Test questions fill in, a lying metric swings.
const QUESTIONS = Array.from({ length: 23 }, (_, n) => n);
const IMPROVED = [0, 2, 3, 5, 7, 8, 10, 13, 14, 16, 19, 20, 22];
const SWING = "M0 120 L50 150 L100 168 L150 70 L200 34 L250 128 L300 150 L360 96";

const FIGURES = [
  {
    fig: "3x",
    text: "faster chat replies on the support agent. A 45-second wait ran on every message. Now it's 15 seconds mid-conversation.",
  },
  { fig: "60→5", text: "minutes for a credit analysis: about an hour before, as little as 5 with my pipeline over 5+ credit bureaus." },
  {
    fig: "10→100",
    text: "credit operations a day: about 10 before, up to 100 once the heavy work moved to RabbitMQ and Celery workers.",
  },
  {
    fig: "0.0205",
    text: "MAE, the best result of my research, from plain DES on visceral leishmaniasis with HIV. No single model won everywhere.",
  },
];

export function GoldenSet() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);

  return (
    <main className="vc" ref={root}>
      <header className="vc-top">
        <span>{profile.name}</span>
        <span>{profile.role}</span>
      </header>

      <section className="vc-hero">
        <h1>{profile.headline}</h1>
        <p>{profile.lede}</p>
      </section>

      <section className="vc-scene scene" aria-label="The search fix">
        <div className="vc-sticky">
          <h2 className="vc-label">The search fix</h2>
          <svg
            className="vc-grid"
            viewBox="0 0 352 236"
            role="img"
            aria-label="23 test questions. 13 of them now get a document the agent used to miss."
          >
            {QUESTIONS.map((n) => {
              const x = (n % 6) * 60;
              const y = Math.floor(n / 6) * 62;
              const hit = IMPROVED.indexOf(n);
              return (
                <g key={n}>
                  <rect x={x + 1} y={y + 1} width={48} height={48} pathLength={1} className="draw" style={step(Math.floor(n / 6) * 0.5)} />
                  {hit >= 0 && (
                    <rect x={x + 7} y={y + 7} width={36} height={36} className="vc-hit fade-in" style={step(2 + hit * 0.45)} />
                  )}
                </g>
              );
            })}
          </svg>
          <p className="vc-big">
            13 <span>of</span> 23
          </p>
          <p className="vc-note">
            test questions now find a document the agent used to miss. The right one ranks 1st or 2nd instead of 3rd.
          </p>
        </div>
      </section>

      <section className="vc-scene vc-scene-short scene" aria-label="The metric that lied">
        <div className="vc-sticky">
          <h2 className="vc-label">The metric that lied</h2>
          <svg className="vc-chart" viewBox="0 0 360 200" role="img" aria-label="A dashboard line swings up and down 4x while the bot line stays flat.">
            <path d="M0 196 H360" className="vc-axis" />
            <path d={SWING} pathLength={1} className="draw vc-swing" style={step(0)} />
            <text x={204} y={24} className="vc-chart-label fade-in" style={step(2)}>
              dashboard metric
            </text>
            <path d="M0 110 H360" pathLength={1} className="draw vc-flat" style={step(4)} />
            <text x={4} y={100} className="vc-chart-label fade-in" style={step(5)}>
              bot changes: none
            </text>
          </svg>
          <p className="vc-note">
            The dashboard number swung 4x in three weeks while the bot hadn't changed at all. I replaced it with a metric
            that counts real resolutions: no escalation, no reopen within 7 days, no human reply.
          </p>
        </div>
      </section>

      <section className="vc-figures">
        {FIGURES.map((f) => (
          <article key={f.fig} className="reveal">
            <p className="vc-fig">{f.fig}</p>
            <p>{f.text}</p>
          </article>
        ))}
      </section>

      <section className="vc-work">
        <h2 className="vc-label">Work</h2>
        {cases.map((c) => (
          <article key={c.id} className="reveal">
            <h3>{c.title}</h3>
            <div>
              <p>{c.summary}</p>
              <p className="vc-meta">
                {c.when}. {c.stack}
              </p>
            </div>
          </article>
        ))}
      </section>

      <section className="vc-contact">
        <h2 className="vc-label">Write to me</h2>
        <a className="vc-mail" href={`mailto:${profile.email}`}>
          {profile.email}
        </a>
        <p className="vc-links">
          <a href={profile.linkedin}>LinkedIn</a>
          <a href={profile.github}>GitHub</a>
        </p>
        <p className="vc-open">{profile.open}</p>
      </section>
    </main>
  );
}
