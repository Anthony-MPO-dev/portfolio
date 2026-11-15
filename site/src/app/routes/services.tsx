import { useRef } from "react";
import { SiteHeader } from "@/components/site-header";
import { contact } from "@/content/profile";
import { servicesPage } from "@/content/services";
import { Calculator } from "@/features/services/calculator";
import { BlockersChapter, PayoffChapter, StallChapter } from "@/features/services/chapters";
import { Offer } from "@/features/services/offer";
import "@/features/services/services.css";
import { useDecode } from "@/hooks/use-decode";
import { useLang } from "@/hooks/use-lang";
import { useReveal } from "@/hooks/use-reveal";
import { alternates, langOf, pathIn, SITE } from "@/lib/lang";

// The /services page of Insight AI & Automation, one screen per chapter: the opening, why most AI stalls, why it
// stalls, what it pays back once it ships (market figures with their sources), the four services with the author's
// own results, and the calculator on the visitor's numbers. Texts and figures come from content/services.ts, in the
// page's language (/services in English, /pt/services in Portuguese).

export function meta({ location }: { location: { pathname: string } }) {
  const lang = langOf(location.pathname);
  const { meta, intro } = servicesPage[lang];
  const url = SITE + pathIn(lang, "/services");
  const title = `${meta.title}, ${contact.name}`;
  const description = intro.title;
  return [
    { title },
    { name: "description", content: description },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
    { property: "og:type", content: "website" },
    { property: "og:url", content: url },
    { property: "og:locale", content: lang === "pt" ? "pt_BR" : "en_US" },
    { tagName: "link", rel: "canonical", href: url },
    ...alternates("/services"),
  ];
}

export default function Services() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);
  useDecode(root);
  const { intro } = servicesPage[useLang()];
  const mail = `mailto:${contact.email}`;

  return (
    <>
      <SiteHeader />
      <main ref={root} className="svc">
        <section className="svc-hero">
          <p className="label">{intro.label}</p>
          <h1 className="svc-title">{intro.title}</h1>
          <p className="svc-who">{intro.who}</p>
        </section>
        <StallChapter />
        <BlockersChapter />
        <PayoffChapter />
        <Offer />
        <Calculator mail={mail} />
      </main>
    </>
  );
}
