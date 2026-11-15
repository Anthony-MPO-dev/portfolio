import { CountUp } from "@/components/count-up";
import { useLang } from "@/hooks/use-lang";
import { step } from "@/lib/step";
import "./support-agent.css";

// Support agent, the search fix: 23 test questions draw in, then the 13 that now find the right document fill red.
const QUESTIONS = Array.from({ length: 23 }, (_, n) => n);
const IMPROVED = [0, 2, 3, 5, 7, 8, 10, 13, 14, 16, 19, 20, 22];

const COPY = {
  en: {
    label: "The search fix",
    drawing: "23 test questions. 13 of them now get a document the agent used to miss.",
    of: "of",
    note: "test questions now find a document the agent used to miss. The right one ranks 1st or 2nd instead of 3rd.",
  },
  pt: {
    label: "A correção da busca",
    drawing: "23 perguntas de teste. 13 delas agora recebem um documento que o agente perdia.",
    of: "de",
    note: "perguntas de teste agora acham um documento que o agente perdia. O certo aparece em 1º ou 2º lugar, e não mais em 3º.",
  },
};

export function SearchFixScene() {
  const t = COPY[useLang()];
  return (
    <section className="scene" aria-label={t.label}>
      <div className="stage agent-stage">
        <h2 className="label">{t.label}</h2>
        <svg
          className="agent-svg agent-grid"
          viewBox="0 0 352 236"
          role="img"
          aria-label={t.drawing}
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
          <CountUp text="13" /> <span>{t.of}</span> 23
        </p>
        <p className="note">{t.note}</p>
      </div>
    </section>
  );
}
