import { PrototypeBar } from "@/components/prototype-bar";
import { GoldenSet } from "@/features/prototype-c/golden-set";

export function meta() {
  return [{ title: "Anthony Muniz, AI & Backend Engineer" }];
}

export function links() {
  return [
    { rel: "stylesheet", href: "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&display=swap" },
  ];
}

export default function DirectionC() {
  return (
    <>
      <GoldenSet />
      <PrototypeBar current="C" />
    </>
  );
}
