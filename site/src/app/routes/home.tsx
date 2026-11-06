import { Link } from "react-router";
import { DIRECTIONS } from "@/components/prototype-bar";

export function meta() {
  return [{ title: "Anthony Muniz, site directions" }];
}

export default function Home() {
  return (
    <main className="home">
      <p className="home-kicker">anthonymuniz.dev, version 0</p>
      <h1>Three directions. Pick one.</h1>
      <ol>
        {DIRECTIONS.map((d) => (
          <li key={d.key}>
            <Link to={d.path}>
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
