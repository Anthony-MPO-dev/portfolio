import { Link } from "react-router";

export function meta() {
  return [{ title: "Anthony Muniz, site directions" }];
}

const directions = [
  { to: "/a", key: "A", name: "Schematic", note: "Light, like an engineering drawing. The credit pipeline draws itself as you scroll." },
  { to: "/b", key: "B", name: "Logstream", note: "Terminal and timeline. LogStream's flow, and healthmon closing the gate." },
  { to: "/c", key: "C", name: "Golden set", note: "Editorial, giant numbers. The 13 of 23 test questions fill in as you scroll." },
];

export default function Home() {
  return (
    <main className="home">
      <p className="home-kicker">anthonymuniz.dev, version 0</p>
      <h1>Three directions. Pick one.</h1>
      <ol>
        {directions.map((d) => (
          <li key={d.key}>
            <Link to={d.to}>
              <span className="home-key">{d.key}</span>
              <span>
                <strong>{d.name}</strong>
                <span>{d.note}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </main>
  );
}
