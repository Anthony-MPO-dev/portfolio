import { CountUp } from "@/components/count-up";
import { step } from "@/lib/step";
import "./support-agent.css";

// Support agent, the search fix: 23 test questions draw in, then the 13 that now find the right document fill red.
const QUESTIONS = Array.from({ length: 23 }, (_, n) => n);
const IMPROVED = [0, 2, 3, 5, 7, 8, 10, 13, 14, 16, 19, 20, 22];

export function SearchFixScene() {
  return (
    <section className="scene" aria-label="The search fix">
      <div className="stage agent-stage">
        <h2 className="label">The search fix</h2>
        <svg
          className="agent-svg agent-grid"
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
                  <rect x={x + 7} y={y + 7} width={36} height={36} className="agent-hit fade-in" style={step(2 + hit * 0.45)} />
                )}
              </g>
            );
          })}
        </svg>
        <p className="big">
          <CountUp text="13" /> <span>of</span> 23
        </p>
        <p className="note">
          test questions now find a document the agent used to miss. The right one ranks 1st or 2nd instead of 3rd.
        </p>
      </div>
    </section>
  );
}
