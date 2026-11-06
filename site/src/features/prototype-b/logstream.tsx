import { useRef } from "react";
import { cases, profile } from "@/content/profile";
import { useReveal } from "@/hooks/use-reveal";
import { step } from "@/lib/step";
import "./logstream.css";

// PROTOTYPE direction B: terminal and timeline. LogStream's flow draws itself, then healthmon closes the gate.
const LOG = [
  ["INFO", "worker_core", "bureau lookup ok"],
  ["INFO", "agent", "batch sent over gRPC"],
  ["WARN", "healthmon", "external API errors rising"],
  ["INFO", "server", "fan-out to dashboards"],
  ["ERROR", "worker_quick", "timeout calling external API"],
  ["WARN", "healthmon", "threshold crossed, gate closed"],
  ["INFO", "healthmon", "service stable, gate open"],
  ["INFO", "worker_core", "report generated"],
];

const BOXES = [
  { y: 10, label: ".log files", note: "" },
  { y: 110, label: "agent, Go", note: "fsnotify, ring buffer" },
  { y: 230, label: "server, Go", note: "JSONL, pub/sub" },
  { y: 350, label: "dashboard", note: "React, live" },
];

export function Logstream() {
  const root = useRef<HTMLDivElement>(null);
  useReveal(root);

  return (
    <div className="vb" ref={root}>
      <section className="vb-hero">
        <div>
          <p className="vb-prompt">$ whoami</p>
          <p className="vb-name">
            {profile.name}, {profile.role}
          </p>
          <h1>{profile.headline}</h1>
          <p className="vb-lede">{profile.lede}</p>
        </div>
        <div className="vb-log" aria-hidden="true">
          <div className="vb-log-track">
            {[...LOG, ...LOG].map(([level, source, msg], n) => (
              <p key={n} className={`vb-line vb-${level.toLowerCase()}`}>
                <span>{level.padEnd(5)}</span> <span>{source.padEnd(12)}</span> {msg}
              </p>
            ))}
          </div>
        </div>
      </section>

      <section className="vb-scene scene" aria-label="How LogStream works">
        <div className="vb-sticky">
          <ol className="vb-steps">
            <li className="fade-in" style={step(0)}>The agent tails log files next to each worker.</li>
            <li className="fade-in" style={step(2)}>Batches go to the server over gRPC.</li>
            <li className="fade-in" style={step(4)}>The dashboard updates live over WebSocket.</li>
            <li className="fade-in" style={step(6)}>
              When an external API keeps failing, healthmon closes the gate on new requests. Retries alone kept hitting a
              service that was already down.
            </li>
          </ol>
          <svg
            className="vb-svg"
            viewBox="0 0 400 600"
            role="img"
            aria-label="Log files go to a Go agent, then over gRPC to a Go server, then over WebSocket to a dashboard. Below, an error rate bar fills past a threshold and a gate closes in front of the external API."
          >
            {BOXES.map((b, n) => (
              <g key={b.label}>
                <rect x={100} y={b.y} width={200} height={44} rx={6} pathLength={1} className="draw" style={step(n * 1.5)} />
                <text x={200} y={b.y + 27} textAnchor="middle" className="vb-node fade-in" style={step(n * 1.5 + 0.5)}>
                  {b.label}
                </text>
                {b.note && (
                  <text x={200} y={b.y + 62} textAnchor="middle" className="vb-note fade-in" style={step(n * 1.5 + 1)}>
                    {b.note}
                  </text>
                )}
              </g>
            ))}
            <path d="M200 54 V110" pathLength={1} className="draw vb-wire" style={step(0.5)} />
            <path d="M200 174 V230" pathLength={1} className="draw vb-wire" style={step(2)} />
            <text x={212} y={208} className="vb-proto fade-in" style={step(2.5)}>
              gRPC
            </text>
            <path d="M200 294 V350" pathLength={1} className="draw vb-wire" style={step(3.5)} />
            <text x={212} y={328} className="vb-proto fade-in" style={step(4)}>
              WebSocket
            </text>

            <text x={20} y={448} className="vb-note fade-in" style={step(6)}>
              healthmon: external API error rate
            </text>
            <rect x={20} y={460} width={360} height={12} pathLength={1} className="draw" style={step(6)} />
            <rect x={20} y={460} width={360} height={12} className="vb-errfill" style={step(6.5)} />
            <path d="M272 452 V480" className="vb-threshold" />
            <path d="M20 545 H236" pathLength={1} className="draw vb-wire" style={step(7)} />
            <text x={20} y={532} className="vb-note fade-in" style={step(7)}>
              new requests
            </text>
            <path d="M250 520 V570" className="vb-gate" style={step(8)} />
            <rect x={278} y={521} width={102} height={48} rx={6} pathLength={1} className="draw" style={step(7)} />
            <text x={329} y={550} textAnchor="middle" className="vb-node-small fade-in" style={step(7.5)}>
              external API
            </text>
            <text x={250} y={596} textAnchor="middle" className="vb-note fade-out" style={step(8)}>
              gate open
            </text>
            <text x={250} y={596} textAnchor="middle" className="vb-warn-text fade-in" style={step(8.5)}>
              gate closed
            </text>
          </svg>
        </div>
      </section>

      <section className="vb-work">
        <p className="vb-prompt">$ ls ~/work</p>
        <ol className="vb-tl">
          {cases.map((c) => (
            <li key={c.id} className="reveal">
              <p className="vb-when">{c.when}</p>
              <h3>{c.title}</h3>
              <p>{c.summary}</p>
              <ul>
                {c.numbers.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </section>

      <section className="vb-contact">
        <p className="vb-prompt">$ contact anthony</p>
        <dl>
          <dt>email</dt>
          <dd>
            <a href={`mailto:${profile.email}`}>{profile.email}</a>
          </dd>
          <dt>linkedin</dt>
          <dd>
            <a href={profile.linkedin}>{profile.linkedinLabel}</a>
          </dd>
          <dt>github</dt>
          <dd>
            <a href={profile.github}>{profile.githubLabel}</a>
          </dd>
        </dl>
        <p className="vb-open">{profile.open}</p>
      </section>
    </div>
  );
}
