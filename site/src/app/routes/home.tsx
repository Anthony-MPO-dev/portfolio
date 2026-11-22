import { Fragment, useRef } from "react";
import { Link } from "react-router";
import portrait from "@/assets/portrait-168.webp";
import { CountUp } from "@/components/count-up";
import { FireFigure } from "@/components/fire-figure";
import { SiteHeader } from "@/components/site-header";
import { contact, home } from "@/content/profile";
import { BotTests } from "@/features/bot-tests/bot-tests";
import { PipelineScene } from "@/features/credit-pipeline/pipeline-scene";
import { FactSearch } from "@/features/fact-search/fact-search";
import { MatrixRain } from "@/features/matrix-rain/rain";
import { MetricScene } from "@/features/support-agent/metric-scene";
import { SearchFixScene } from "@/features/support-agent/search-fix-scene";
import { useDecode } from "@/hooks/use-decode";
import { useLang } from "@/hooks/use-lang";
import { useReveal } from "@/hooks/use-reveal";
import { TYPED_IN_MS } from "@/lib/entry";
import { langOf, pageLinks, pathIn } from "@/lib/lang";
import "./home.css";
import "./home-entrance.css";

// The home page, composed here from the features: header, hero (signed with the author's photo), the three scroll
// scenes (support agent, credit pipeline), the big figures, the work list, how the bot is tested, the fact search,
// Services and contact.
// Texts and lists come from content/profile.ts, in the page's language (/ in English, /pt/ in Portuguese). The
// sections marked .typed type themselves in (home-entrance.css); the labels decode (useDecode) and the character rain
// falls behind the hero.

export function meta({ location }: { location: { pathname: string } }) {
  const lang = langOf(location.pathname);
  const { profile } = home[lang];
  const { url, tags } = pageLinks(lang, "/");
  const title = `${contact.name}, ${profile.role}`;
  return [
    { title },
    { name: "description", content: profile.lede },
    { property: "og:title", content: title },
    { property: "og:description", content: profile.lede },
    { property: "og:type", content: "website" },
    ...tags,
    // The card search engines read about the author (schema.org Person): only facts already on the page.
    {
      "script:ld+json": {
        "@context": "https://schema.org",
        "@type": "Person",
        name: contact.name,
        jobTitle: profile.role,
        description: profile.lede,
        url,
        email: `mailto:${contact.email}`,
        address: { "@type": "PostalAddress", addressCountry: "BR" },
        sameAs: [contact.linkedin, contact.github],
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
  const lang = useLang();
  const { profile, labels, figures, cases, services } = home[lang];
  const mail = `mailto:${contact.email}`;

  return (
    <>
      <SiteHeader />

      <main ref={root}>
        <section className="hero typed">
          <p className="label">{profile.role}</p>
          <Headline text={profile.headline} />
          <p className="hero-lede">{profile.lede}</p>
          <div className="byline">
            {/* 168 px: sharp at 56 px up to a 3x screen, 5 KB */}
            <img className="byline-photo" src={portrait} width={168} height={210} decoding="async" alt={contact.name} />
            <p>
              <strong>{contact.name}</strong>
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

        <section className="figures typed" aria-label={labels.results}>
          {figures.map((f) => (
            <article key={f.fig}>
              {/^\d+x$/.test(f.fig) ? (
                <FireFigure text={f.fig} replay={labels.replay} hint={labels.hint} />
              ) : (
                <p className="figure">
                  {f.from === undefined ? f.fig : <CountUp text={f.fig} from={f.from} delay={TYPED_IN_MS} ms={1200} />}
                </p>
              )}
              <p>{f.text}</p>
            </article>
          ))}
        </section>

        <section className="work typed">
          <h2 className="label">{labels.work}</h2>
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

        <BotTests />
        {/* keyed: / and /pt/ share this module, so the header's EN | PT starts the search over in the new language */}
        <FactSearch key={lang} start={lang} />

        <section className="services typed">
          <h2 className="label">
            {labels.services}: {services.company}
          </h2>
          <p className="services-lead">{services.lead}</p>
          <p className="services-text">{services.offer}</p>
          <p className="services-text">
            {services.proof} {services.terms}
          </p>
          <a className="services-cta" href={mail}>
            {services.cta} <span className="arrow" aria-hidden="true">&rarr;</span>
          </a>
          <Link className="services-more" to={pathIn(lang, "/services")}>
            {services.more} <span className="arrow" aria-hidden="true">&rarr;</span>
          </Link>
        </section>

        <section className="contact typed">
          <h2 className="label">{labels.contact}</h2>
          <a className="contact-mail" href={mail}>
            {contact.email}
            <span className="arrow" aria-hidden="true">&#8599;</span>
          </a>
          <p className="contact-links">
            <a href={contact.linkedin}>LinkedIn</a>
            <a href={contact.github}>GitHub</a>
          </p>
          <p className="contact-open">{profile.open}</p>
        </section>
      </main>
    </>
  );
}
