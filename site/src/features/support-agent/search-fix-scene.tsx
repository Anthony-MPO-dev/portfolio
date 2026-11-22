import { CountUp } from "@/components/count-up";
import { useLang } from "@/hooks/use-lang";
import type { Lang } from "@/lib/lang";
import { step } from "@/lib/step";
import "./support-agent.css";

// Support agent, the search fix: 23 test questions draw in, then the 13 that now find the right document fill in, with
// a legend under the squares. The Portuguese legend and note wait for the author's review (legend null: not drawn).
// Public API: SearchFixScene. Used by: app/routes/home.tsx.
const QUESTIONS = Array.from({ length: 23 }, (_, n) => n);
const IMPROVED = [0, 2, 3, 5, 7, 8, 10, 13, 14, 16, 19, 20, 22];

const COPY: Record<Lang, { label: string; drawing: string; of: string; note: string; legend: [string, string] | null }> = {
  en: {
    label: "The search fix",
    drawing: "23 test questions. For 13 of them the right document now comes back 1st or 2nd.",
    of: "of",
    note: "test questions used to miss the right document. Now it comes back 1st or 2nd. I got there by deleting index and duplicate pages from the agent's knowledge base.",
    legend: ["A test question", "Now finds the right document"],
  },
  pt: {
    label: "A correção da busca",
    drawing: "23 perguntas de teste. 13 delas agora recebem um documento que o agente perdia.",
    of: "de",
    note: "perguntas de teste agora acham um documento que o agente perdia. O certo aparece em 1º ou 2º lugar, e não mais em 3º.",
    legend: null,
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
          viewBox={`0 0 352 ${t.legend ? 292 : 236}`}
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
          {t.legend && (
            <g className="fade-in" style={step(1.5)}>
              <g className="agent-legend">
                <rect x={1} y={250} width={14} height={14} />
                <text className="agent-chart-label" x={24} y={262}>
                  {t.legend[0]}
                </text>
                <rect x={1} y={274} width={14} height={14} className="agent-hit" />
                <text className="agent-chart-label" x={24} y={286}>
                  {t.legend[1]}
                </text>
              </g>
            </g>
          )}
        </svg>
        <p className="big">
          <CountUp text="13" /> <span>{t.of}</span> 23
        </p>
        <p className="note">{t.note}</p>
      </div>
    </section>
  );
}
