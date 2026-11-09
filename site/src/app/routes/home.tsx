import { Fragment, useRef } from "react";
import portrait from "@/assets/portrait-168.webp";
import { FireFigure } from "@/components/fire-figure";
import { ThemeToggle } from "@/components/theme-toggle";
import { cases, figures, profile, services } from "@/content/profile";
import { PipelineScene } from "@/features/credit-pipeline/pipeline-scene";
import { MatrixRain } from "@/features/matrix-rain/rain";
import { MetricScene } from "@/features/support-agent/metric-scene";
import { SearchFixScene } from "@/features/support-agent/search-fix-scene";
import { useDecode } from "@/hooks/use-decode";
import { useReveal } from "@/hooks/use-reveal";
import "./home.css";
import "./home-entrance.css";

// The one page of the site, composed here from the features: header, hero (signed with the author's photo), the three
// scroll scenes (support agent, credit pipeline), the big figures, the work list, Services and contact. Lists come from
// content/profile.ts. The sections marked .typed type themselves in (home-entrance.css); the labels decode (useDecode)
// and the character rain falls behind the hero.
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
    // The card search engines read about the author (schema.org Person): only facts already on the page.
    {
      "script:ld+json": {
        "@context": "https://schema.org",
        "@type": "Person",
        name: profile.name,
        jobTitle: profile.role,
        description: profile.lede,
        url: SITE_URL,
        email: `mailto:${profile.email}`,
        address: { "@type": "PostalAddress", addressCountry: "BR" },
        sameAs: [profile.linkedin, profile.github],
        knowsAbout: ["Python", "FastAPI", "LLMs", "RAG", "Agentic AI", "LLM evaluation", "n8n", "Celery", "Redis", "Docker"],
      },
    },
  ];
}

// The headline split into words, each with its index, so the entrance can type it word by word.
function Headline({ text }: { text: string }) {
  return (
    <h1>
      {text.split(" ").map((word, i) => (
        <Fragment key={i}>
          <span className="w" style={{ "--i": i } as React.CSSProperties}>
            <span>{word}</span>
          </span>{" "}
        </Fragment>
      ))}
    </h1>
  );
}

export default function Home() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);
  useDecode(root);
  const mail = `mailto:${profile.email}`;

  return (
    <>
      <header className="top">
        <span>{profile.name}</span>
        <span className="top-status">{profile.status}</span>
        <ThemeToggle />
      </header>

      <main ref={root}>
        <section className="hero typed">
          <p className="label">{profile.role}</p>
          <Headline text={profile.headline} />
          <p className="hero-lede">{profile.lede}</p>
          <div className="byline">
            {/* 168 px: sharp at 56 px up to a 3x screen, 5 KB */}
            <img className="byline-photo" src={portrait} width={168} height={210} decoding="async" alt={profile.name} />
            <p>
              <strong>{profile.name}</strong>
              <span>
                {profile.role}. {profile.based}
              </span>
            </p>
          </div>
          <MatrixRain />
        </section>

        <SearchFixScene />
        <MetricScene />
        <PipelineScene />

        <section className="figures typed" aria-label="Results">
          {figures.map((f) => (
            <article key={f.fig}>
              {/^\d+x$/.test(f.fig) ? <FireFigure text={f.fig} /> : <p className="figure">{f.fig}</p>}
              <p>{f.text}</p>
            </article>
          ))}
        </section>

        <section className="work typed">
          <h2 className="label">Work</h2>
          {cases.map((c) => (
            <article key={c.id} className="row">
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

        <section className="services typed">
          <h2 className="label">Services, {services.company}</h2>
          <p className="services-lead">{services.lead}</p>
          <p className="services-text">{services.offer}</p>
          <p className="services-text">
            {services.proof} {services.terms}
          </p>
          <a className="services-cta" href={mail}>
            {services.cta} <span className="arrow" aria-hidden="true">&rarr;</span>
          </a>
        </section>

        <section className="contact typed">
          <h2 className="label">Contact me</h2>
          <a className="contact-mail" href={mail}>
            {profile.email}
            <span className="arrow" aria-hidden="true">&#8599;</span>
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
