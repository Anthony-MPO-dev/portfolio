import { useLang } from "@/hooks/use-lang";
import { step } from "@/lib/step";
import "./support-agent.css";

// Support agent, the metric that lied: the dashboard line swings while the "bot changes" line stays flat.
const SWING = "M0 120 L50 150 L100 168 L150 70 L200 34 L250 128 L300 150 L360 96";

export const COPY = {
  en: {
    label: "The metric that lied",
    drawing: "A dashboard line swings up and down 4x while the bot line stays flat.",
    metric: "dashboard metric",
    bot: "bot changes: none",
    note: "The dashboard number swung 4x in 3 weeks while the bot hadn't changed at all. I replaced it with a metric that counts real resolutions: no escalation, no reopening within 7 days, no human reply.",
  },
  pt: {
    label: "A métrica que mentia",
    drawing: "Uma linha do painel sobe e desce 4x enquanto a linha do bot fica reta.",
    metric: "métrica do painel",
    bot: "mudanças no bot: nenhuma",
    note: "O número do painel oscilou 4x em 3 semanas sem o bot ter mudado nada. Troquei por uma métrica que conta resoluções reais: sem escalar, sem reabrir em 7 dias, sem resposta humana.",
  },
};

export function MetricScene() {
  const t = COPY[useLang()];
  return (
    <section className="scene" aria-label={t.label}>
      <div className="stage agent-stage">
        <h2 className="label">{t.label}</h2>
        <svg
          className="agent-svg"
          viewBox="0 0 360 200"
          role="img"
          aria-label={t.drawing}
        >
          <path d="M0 196 H360" className="agent-axis" />
          <path d={SWING} pathLength={1} className="draw agent-swing" style={step(0)} />
          <text x={204} y={24} className="agent-chart-label fade-in" style={step(2)}>
            {t.metric}
          </text>
          <path d="M0 110 H360" pathLength={1} className="draw agent-flat" style={step(4)} />
          <text x={4} y={100} className="agent-chart-label fade-in" style={step(5)}>
            {t.bot}
          </text>
        </svg>
        <p className="note">{t.note}</p>
      </div>
    </section>
  );
}
