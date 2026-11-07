import { useRef } from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cases, profile, services } from "@/content/profile";
import { PipelineScene } from "@/features/credit-pipeline/pipeline-scene";
import { MetricScene } from "@/features/support-agent/metric-scene";
import { SearchFixScene } from "@/features/support-agent/search-fix-scene";
import { useReveal } from "@/hooks/use-reveal";
import "./home.css";

// The one page of the site: hero, the three scroll scenes (support agent, credit pipeline), the big figures, the
// work list, Services and contact. Numbers come from content/profile.ts, which follows the public facts.
const FIGURES = [
  {
    fig: "3x",
    text: "faster chat replies on the support agent. A 45-second wait ran on every message. Now it's 15 seconds mid-conversation.",
  },
  {
    fig: "0.0205",
    text: "MAE, the best result of my research, from plain DES on visceral leishmaniasis with HIV. No single model won everywhere.",
  },
];

export function HomePage() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);

  return (
    <>
      <header className="top">
        <span>{profile.name}</span>
        <span className="top-role">{profile.role}</span>
        <ThemeToggle />
      </header>

      <main ref={root}>
        <section className="hero">
          <h1>{profile.headline}</h1>
          <p>{profile.lede}</p>
        </section>

        <SearchFixScene />
        <MetricScene />
        <PipelineScene />

        <section className="figures" aria-label="Results">
          {FIGURES.map((f) => (
            <article key={f.fig} className="reveal">
              <p className="figure">{f.fig}</p>
              <p>{f.text}</p>
            </article>
          ))}
        </section>

        <section className="work">
          <h2 className="label">Work</h2>
          {cases.map((c) => (
            <article key={c.id} className="row reveal">
              <h3>{c.title}</h3>
              <div>
                <p>{c.summary}</p>
                <p className="meta">
                  {c.when}. {c.stack}
                </p>
              </div>
            </article>
          ))}
        </section>

        <section className="services">
          <h2 className="label">Services, {services.company}</h2>
          <p className="services-lead">{services.lead}</p>
          <p className="services-intro">{services.intro}</p>
          {services.offers.map((o) => (
            <article key={o.title} className="row reveal">
              <h3>{o.title}</h3>
              <p>{o.text}</p>
            </article>
          ))}
          <p className="services-proof">
            {services.proof} {services.terms}
          </p>
          <a className="services-cta" href={`mailto:${profile.email}`}>
            {services.cta}
          </a>
        </section>

        <section className="contact">
          <h2 className="label">Write to me</h2>
          <a className="contact-mail" href={`mailto:${profile.email}`}>
            {profile.email}
          </a>
          <p className="contact-links">
            <a href={profile.linkedin}>LinkedIn</a>
            <a href={profile.github}>GitHub</a>
          </p>
          <p className="contact-open">{profile.open}</p>
        </section>
      </main>
    </>
  );
}
