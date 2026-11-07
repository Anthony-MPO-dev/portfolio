import { step } from "@/lib/step";
import "./pipeline-scene.css";

// Credit pipeline scroll scene: five bureaus feed a queue, workers run the analysis, the report comes out and the
// time drops from about an hour to 5 minutes. Drawn in code, part by part, so each piece can animate on its own.
const BUREAUS = [0, 1, 2, 3, 4];
const WORKERS = [80, 200, 320];

export function PipelineScene() {
  return (
    <section className="scene pipeline" aria-label="The credit pipeline">
      <div className="stage pipeline-stage">
        <div>
          <h2 className="label">The credit pipeline</h2>
          <p className="note">
            Five credit bureaus in, one report out. A credit analysis took about an hour, and this pipeline gets it done in
            as little as 5 minutes. Moving the heavy work to RabbitMQ and Celery workers took capacity from about 10 to up
            to 100 operations a day.
          </p>
        </div>
        <svg
          className="pipeline-svg"
          viewBox="0 0 400 620"
          role="img"
          aria-label="Five credit bureaus feed a RabbitMQ queue, three workers run the analysis and a report comes out. The time drops from about an hour to as little as 5 minutes."
        >
          <text x="200" y="14" textAnchor="middle" className="pipeline-small">
            5+ credit bureaus
          </text>
          {BUREAUS.map((b) => {
            const x = 10 + b * 78;
            return (
              <g key={b}>
                <rect x={x} y={26} width={66} height={40} pathLength={1} className="draw" style={step(0)} />
                <text x={x + 33} y={51} textAnchor="middle" className="pipeline-node fade-in" style={step(1)}>
                  B{b + 1}
                </text>
                <path
                  d={`M${x + 33} 66 C ${x + 33} 130, 200 120, 200 186`}
                  pathLength={1}
                  className="draw pipeline-wire"
                  style={step(1)}
                />
              </g>
            );
          })}
          <rect x={110} y={186} width={180} height={56} pathLength={1} className="draw" style={step(2)} />
          <text x={200} y={219} textAnchor="middle" className="pipeline-node fade-in" style={step(3)}>
            RabbitMQ queue
          </text>
          {WORKERS.map((cx) => (
            <g key={cx}>
              <path d={`M200 242 C 200 280, ${cx} 270, ${cx} 316`} pathLength={1} className="draw pipeline-wire" style={step(3)} />
              <rect x={cx - 55} y={316} width={110} height={48} pathLength={1} className="draw" style={step(4)} />
              <text x={cx} y={345} textAnchor="middle" className="pipeline-node fade-in" style={step(5)}>
                worker
              </text>
              <path d={`M${cx} 364 C ${cx} 410, 200 400, 200 446`} pathLength={1} className="draw pipeline-wire" style={step(5)} />
            </g>
          ))}
          <rect x={120} y={446} width={160} height={56} pathLength={1} className="draw pipeline-report" style={step(6)} />
          <text x={200} y={479} textAnchor="middle" className="pipeline-node fade-in" style={step(7)}>
            report
          </text>
          <text x={200} y={600} textAnchor="middle" className="pipeline-time fade-out" style={step(7)}>
            about 1 hour
          </text>
          <text x={200} y={600} textAnchor="middle" className="pipeline-time pipeline-time-new fade-in" style={step(8)}>
            down to 5 min
          </text>
        </svg>
      </div>
    </section>
  );
}
