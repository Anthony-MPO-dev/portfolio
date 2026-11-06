import { PrototypeBar } from "@/components/prototype-bar";
import { Logstream } from "@/features/prototype-b/logstream";

export function meta() {
  return [{ title: "Anthony Muniz, AI & Backend Engineer" }];
}

export function links() {
  return [
    {
      rel: "stylesheet",
      href: "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap",
    },
  ];
}

export default function DirectionB() {
  return (
    <>
      <Logstream />
      <PrototypeBar current="B" />
    </>
  );
}
