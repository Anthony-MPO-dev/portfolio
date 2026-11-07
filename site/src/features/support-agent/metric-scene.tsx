import { step } from "@/lib/step";
import "./support-agent.css";

// Support agent, the metric that lied: the dashboard line swings while the "bot changes" line stays flat.
const SWING = "M0 120 L50 150 L100 168 L150 70 L200 34 L250 128 L300 150 L360 96";

export function MetricScene() {
  return (
    <section className="scene scene-short" aria-label="The metric that lied">
      <div className="stage">
        <h2 className="label">The metric that lied</h2>
        <svg
          className="agent-svg"
          viewBox="0 0 360 200"
          role="img"
          aria-label="A dashboard line swings up and down 4x while the bot line stays flat."
        >
          <path d="M0 196 H360" className="agent-axis" />
          <path d={SWING} pathLength={1} className="draw agent-swing" style={step(0)} />
          <text x={204} y={24} className="agent-chart-label fade-in" style={step(2)}>
            dashboard metric
          </text>
          <path d="M0 110 H360" pathLength={1} className="draw agent-flat" style={step(4)} />
          <text x={4} y={100} className="agent-chart-label fade-in" style={step(5)}>
            bot changes: none
          </text>
        </svg>
        <p className="note">
          The dashboard number swung 4x in three weeks while the bot hadn't changed at all. I replaced it with a metric that
          counts real resolutions: no escalation, no reopening within 7 days, no human reply.
        </p>
      </div>
    </section>
  );
}
