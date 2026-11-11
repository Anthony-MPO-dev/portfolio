import { useRef } from "react";
import { SiteHeader } from "@/components/site-header";
import { profile } from "@/content/profile";
import { intro } from "@/content/services";
import { Calculator } from "@/features/services/calculator";
import { BlockersChapter, PayoffChapter, StallChapter } from "@/features/services/chapters";
import { Offer } from "@/features/services/offer";
import "@/features/services/services.css";
import { useDecode } from "@/hooks/use-decode";
import { useReveal } from "@/hooks/use-reveal";

// The /services page of Insight AI & Automation, one screen per chapter: the opening, why most AI stalls, why it
// stalls, what it pays back once it ships (market figures with their sources), the four services with the author's
// own results, and the calculator on the visitor's numbers. Texts and figures come from content/services.ts.
const URL = "https://anthonymuniz.dev/services";

export function meta() {
  const title = `Services, ${profile.name}`;
  const description = intro.title;
  return [
    { title },
    { name: "description", content: description },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
    { property: "og:type", content: "website" },
    { property: "og:url", content: URL },
    { tagName: "link", rel: "canonical", href: URL },
  ];
}

export default function Services() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);
  useDecode(root);
  const mail = `mailto:${profile.email}`;

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
