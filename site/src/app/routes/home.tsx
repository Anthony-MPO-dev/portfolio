import { profile } from "@/content/profile";
import { HomePage } from "@/features/home/home-page";

const URL = "https://anthonymuniz.dev/";

export function meta() {
  const title = `${profile.name}, ${profile.role}`;
  return [
    { title },
    { name: "description", content: profile.lede },
    { property: "og:title", content: title },
    { property: "og:description", content: profile.lede },
    { property: "og:type", content: "website" },
    { property: "og:url", content: URL },
    { tagName: "link", rel: "canonical", href: URL },
  ];
}

export default function Home() {
  return <HomePage />;
}
