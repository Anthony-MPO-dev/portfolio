import { PrototypeBar } from "@/components/prototype-bar";
import { Schematic } from "@/features/prototype-a/schematic";

export function meta() {
  return [{ title: "Anthony Muniz, AI & Backend Engineer" }];
}

export function links() {
  return [
    {
      rel: "stylesheet",
      href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;700&display=swap",
    },
  ];
}

export default function DirectionA() {
  return (
    <>
      <Schematic />
      <PrototypeBar current="A" />
    </>
  );
}
