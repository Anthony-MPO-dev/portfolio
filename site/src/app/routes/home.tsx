import { useRef } from "react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cases, figures, profile, services } from "@/content/profile";
import { PipelineScene } from "@/features/credit-pipeline/pipeline-scene";
import { MetricScene } from "@/features/support-agent/metric-scene";
import { SearchFixScene } from "@/features/support-agent/search-fix-scene";
import { useReveal } from "@/hooks/use-reveal";
import "./home.css";

// The one page of the site, composed here from the features: header, hero, the three scroll scenes (support agent,
// credit pipeline), the big figures, the work list, Services and contact. Lists come from content/profile.ts.
const SITE_URL = "https://anthonymuniz.dev/";

export function meta() {
  const title = `${profile.name}, ${profile.role}`;
  return [
    { title },
    { name: "description", content: profile.lede },
    { property: "og:title", content: title },
    { property: "og:description", content: profile.lede },
    { property: "og:type", content: "website" },
    { property: "og:url", content: SITE_URL },
    { tagName: "link", rel: "canonical", href: SITE_URL },
  ];
}

export default function Home() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);
  const mail = `mailto:${profile.email}`;

  return (
    <>
      <header className="top">
        <span>{profile.name}</span>
        <span className="top-status">{profile.status}</span>
        <ThemeToggle />
      </header>

      <main ref={root}>
        <section className="hero">
          <p className="label">{profile.role}</p>
          <h1>{profile.headline}</h1>
          <p className="hero-lede">{profile.lede}</p>
        </section>

        <SearchFixScene />
        <MetricScene />
        <PipelineScene />

        <section className="figures" aria-label="Results">
          {figures.map((f) => (
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
          <p className="services-text">{services.offer}</p>
          <p className="services-text">
            {services.proof} {services.terms}
          </p>
          <a className="services-cta" href={mail}>
            {services.cta}
          </a>
        </section>

        <section className="contact">
          <h2 className="label">Contact me</h2>
          <a className="contact-mail" href={mail}>
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
