import { Link } from "react-router-dom";
import logo from "../assets/images/logo.png";
import SmartMillingContent from "../components/SmartMillingContent";
import { ContactList } from "../components/ContactList";
import { config } from "../config";
import { intro } from "../content/smartMilling";
import { useSeo } from "../lib/seo";
import "./landing.css";

export const LANDING_TITLE =
  "Rice Mill Energy Monitoring System | Smart Milling by RicemillMart";
export const LANDING_DESCRIPTION =
  "Monitor every motor in your rice mill live. RicemillMart's Smart Milling System tracks machine-wise power, energy use, power factor and alerts on one dashboard, so you cut electricity cost and downtime.";

export default function LandingPage() {
  useSeo({
    title: LANDING_TITLE,
    description: LANDING_DESCRIPTION,
    path: "/",
    index: true,
  });

  return (
    <div className="landing">
      <header className="landing-bar">
        <Link to="/" className="landing-brand">
          <img src={logo} alt="RicemillMart.com" width="144" height="71" />
        </Link>
        <nav aria-label="Account">
          <Link className="landing-link" to="/login">
            Sign in
          </Link>
          <Link className="landing-cta" to="/register">
            Create account
          </Link>
        </nav>
      </header>

      <main>
        <section className="landing-hero">
          <p className="landing-eyebrow">{config.company.name}</p>
          <h1>Rice mill energy monitoring and smart milling system</h1>
          <p className="landing-lead">{intro.tagline}</p>
          {intro.paragraphs.map((t) => (
            <p key={t}>{t}</p>
          ))}
          <div className="landing-actions">
            <Link className="landing-cta" to="/register">
              Create account
            </Link>
            <Link className="landing-link" to="/login">
              Sign in to your dashboard
            </Link>
          </div>
          <ContactList />
        </section>
        <SmartMillingContent />
      </main>

      <footer className="landing-foot">
        <span>&copy; {new Date().getFullYear()} {config.company.name} · ricemillmart.com</span>
      </footer>
    </div>
  );
}
