import { useLang } from "@/hooks/use-lang";
import { step } from "@/lib/step";
import "./pipeline-scene.css";

// Credit pipeline scroll scene: five bureaus feed a queue, workers run the analysis, the report comes out and the
// time drops from about an hour to 5 minutes. Drawn in code, part by part, so each piece can animate on its own.
const BUREAUS = [0, 1, 2, 3, 4];
const WORKER_X = [80, 200, 320];

const COPY = {
  en: {
    label: "The credit pipeline",
    note: "Five or more credit bureaus in, one report out. A credit analysis used to take about an hour, and this pipeline gets it done in as fast as 5 minutes. Moving the heavy work to RabbitMQ and Celery workers raised capacity from about 10 to as many as 100 operations a day.",
    drawing:
      "Five or more credit bureaus feed a RabbitMQ queue, workers run the analysis and a report comes out in as fast as 5 minutes, down from about an hour.",
    bureaus: "5+ credit bureaus",
    queue: "RabbitMQ queue",
    worker: "worker",
    report: "report",
    before: "about 1 hour",
    after: "as fast as 5 min",
  },
  pt: {
    label: "O pipeline de crédito",
    note: "Cinco ou mais birôs de crédito entrando, um relatório saindo. Uma análise de crédito levava cerca de uma hora, e este pipeline a entrega em 5 minutos no melhor caso. Passar o trabalho pesado para workers com RabbitMQ e Celery aumentou a capacidade de cerca de 10 para até 100 operações por dia.",
    drawing:
      "Cinco ou mais birôs de crédito alimentam uma fila no RabbitMQ, workers rodam a análise e um relatório sai em 5 minutos no melhor caso, contra cerca de uma hora antes.",
    bureaus: "5+ birôs de crédito",
    queue: "fila RabbitMQ",
    worker: "worker",
    report: "relatório",
    before: "cerca de 1 hora",
    after: "5 min no melhor caso",
  },
};

export function PipelineScene() {
  const t = COPY[useLang()];
  return (
    <section className="scene pipeline" aria-label={t.label}>
      <div className="stage pipeline-stage">
        <div>
          <h2 className="label">{t.label}</h2>
          <p className="note">{t.note}</p>
        </div>
        <svg
          className="pipeline-svg"
          viewBox="0 0 400 620"
          role="img"
          aria-label={t.drawing}
        >
          <text x="200" y="14" textAnchor="middle" className="pipeline-small">
            {t.bureaus}
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
            {t.queue}
          </text>
          {WORKER_X.map((cx) => (
            <g key={cx}>
              <path d={`M200 242 C 200 280, ${cx} 270, ${cx} 316`} pathLength={1} className="draw pipeline-wire" style={step(3)} />
              <rect x={cx - 55} y={316} width={110} height={48} pathLength={1} className="draw" style={step(4)} />
              <text x={cx} y={345} textAnchor="middle" className="pipeline-node fade-in" style={step(5)}>
                {t.worker}
              </text>
              <path d={`M${cx} 364 C ${cx} 410, 200 400, 200 446`} pathLength={1} className="draw pipeline-wire" style={step(5)} />
            </g>
          ))}
          <rect x={120} y={446} width={160} height={56} pathLength={1} className="draw pipeline-report" style={step(6)} />
          <text x={200} y={479} textAnchor="middle" className="pipeline-node fade-in" style={step(7)}>
            {t.report}
          </text>
          <text x={200} y={600} textAnchor="middle" className="pipeline-time fade-out" style={step(7)}>
            {t.before}
          </text>
          <text x={200} y={600} textAnchor="middle" className="pipeline-time pipeline-time-new fade-in" style={step(8)}>
            {t.after}
          </text>
        </svg>
      </div>
    </section>
  );
}
