import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { config, USE_MOCK } from "../config";
import {
  benefits,
  connect,
  founders,
  intelligence,
  intro,
  steps,
} from "../content/smartMilling";
import logo from "../assets/images/logo.png";
import hero from "../assets/images/sm-hero.svg";
import flow from "../assets/images/sm-flow.svg";
import energy from "../assets/images/sm-energy.svg";
import maintenance from "../assets/images/sm-maintenance.svg";
import production from "../assets/images/sm-production.svg";
import wastage from "../assets/images/sm-wastage.svg";
import "./smartmilling.css";

const PICTURES = {
  production: [production, "Bars showing how hard each machine is working"],
  energy: [energy, "Energy used by each machine and the power factor"],
  maintenance: [maintenance, "Running hours and a service reminder"],
};

const ICONS = {
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm10 3a3 3 0 100-6 3 3 0 000 6z",
  bars: "M4 20V10m6 10V4m6 16v-7m4 7H2",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7l1-8z",
  search: "M11 4a7 7 0 100 14 7 7 0 000-14zm9 16l-4-4",
  wrench: "M14 6a4 4 0 005 5l-9 9a2.1 2.1 0 01-3-3l9-9a4 4 0 00-2-2z",
  rupee: "M7 5h10M7 9h10M7 5c5 0 7 2 7 4s-2 4-7 4l7 6",
  screen: "M3 5h18v11H3zM8 20h8M12 16v4",
};
const BenefitIcon = ({ name }) => (
  <svg
    viewBox="0 0 24 24"
    width="26"
    height="26"
    aria-hidden="true"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d={ICONS[name]} />
  </svg>
);

const Soon = () => <span className="sm-soon">Coming soon</span>;

const EMPTY = { name: "", mobile: "", requirement: "", website: "" };

function ContactForm() {
  const [form, setForm] = useState(EMPTY);
  const [state, setState] = useState({ phase: "idle", message: "" });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const ready =
    form.name.trim() &&
    form.mobile.trim() &&
    form.requirement.trim() &&
    state.phase !== "sending";

  async function submit(e) {
    e.preventDefault();
    if (!ready) return;
    setState({ phase: "sending", message: "" });
    try {
      await api.contact.send(form);
      setForm(EMPTY);
      setState({
        phase: "done",
        message: USE_MOCK
          ? "Demo mode: this enquiry was saved in your browser only. It was not sent to anyone."
          : "Thank you. We have received your enquiry and our team will get in touch with you.",
      });
    } catch (err) {
      setState({
        phase: "error",
        message:
          err?.status === 429
            ? "You have sent several enquiries recently. Please try again in an hour, or call us."
            : err?.message || "We could not send your enquiry. Please try again.",
      });
    }
  }

  return (
    <form className="sm-form" onSubmit={submit} noValidate>
      <label>
        <span>
          Name <span aria-hidden="true">*</span>
        </span>
        <input
          value={form.name}
          onChange={set("name")}
          placeholder="Enter your name"
          autoComplete="name"
          maxLength={100}
          required
        />
      </label>
      <label>
        <span>
          Mobile <span aria-hidden="true">*</span>
        </span>
        <input
          value={form.mobile}
          onChange={set("mobile")}
          placeholder="Enter your mobile number"
          autoComplete="tel"
          inputMode="tel"
          maxLength={20}
          required
        />
      </label>
      <label>
        <span>
          Requirement <span aria-hidden="true">*</span>
        </span>
        <textarea
          value={form.requirement}
          onChange={set("requirement")}
          placeholder="Please describe your requirement..."
          rows={4}
          maxLength={2000}
          required
        />
      </label>
      {/* Spam trap: people never see or fill this, simple bots do. */}
      <div className="sm-hp" aria-hidden="true">
        <label>
          Website
          <input
            tabIndex={-1}
            autoComplete="off"
            value={form.website}
            onChange={set("website")}
          />
        </label>
      </div>
      <button className="sm-btn" type="submit" disabled={!ready}>
        {state.phase === "sending" ? "Sending…" : "Submit"}
      </button>
      <p className="sm-note">* All fields are mandatory.</p>
      {state.message && (
        <p className={state.phase === "error" ? "sm-msg bad" : "sm-msg ok"} role="status">
          {state.message}
        </p>
      )}
    </form>
  );
}

export default function SmartMillingPage() {
  const { company } = config;
  const wa = company.whatsapp
    ? `https://wa.me/${company.whatsapp}?text=${encodeURIComponent("Hello, I would like to know more about the Smart Milling System.")}`
    : "";
  return (
    <div className="sm">
      <header className="sm-top">
        <a href="#top" className="sm-brand" aria-label="RicemillMart.com">
          <img src={logo} alt="RicemillMart.com" />
        </a>
        <nav aria-label="Page sections">
          <a href="#how">How it works</a>
          <a href="#benefits">Benefits</a>
          <a href="#about">About us</a>
          <a href="#contact">Contact</a>
          <Link className="sm-login" to="/login">
            Owner login
          </Link>
        </nav>
      </header>

      <main id="top">
        <section className="sm-hero">
          <div>
            <p className="sm-kicker">Smart Milling System</p>
            <h1>{intro.tagline}</h1>
            <p className="sm-lead">{intro.paragraphs[0]}</p>
            <div className="sm-cta">
              <a className="sm-btn" href="#contact">
                Talk to us
              </a>
              <a className="sm-btn ghost" href="#how">
                See how it works
              </a>
            </div>
          </div>
          <img src={hero} alt="A rice mill beside a live monitoring dashboard" />
        </section>

        <section className="sm-section sm-intro">
          {intro.paragraphs.slice(1).map((p) => (
            <p key={p}>{p}</p>
          ))}
        </section>

        <section className="sm-section" aria-labelledby="intel">
          <h2 id="intel">One dashboard. Three kinds of insight.</h2>
          <div className="sm-cards">
            {intelligence.map((c) => (
              <article className="sm-card" key={c.key}>
                <img src={PICTURES[c.key][0]} alt={PICTURES[c.key][1]} loading="lazy" />
                <h3>{c.title}</h3>
                <p>{c.text}</p>
                <ul>
                  {c.points.map((pt) => (
                    <li key={pt.label}>
                      {pt.label} {pt.soon && <Soon />}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="sm-section" id="how" aria-labelledby="how-h">
          <h2 id="how-h">{steps.title}</h2>
          <p className="sm-sub">{steps.text}</p>
          <div className="sm-scroll">
            <img
              className="sm-wide"
              src={flow}
              alt="Energy meters send readings through a gateway and the cloud to your dashboard"
              loading="lazy"
            />
          </div>
        </section>

        <section className="sm-section sm-band" id="benefits" aria-labelledby="ben-h">
          <h2 id="ben-h">{benefits.title}</h2>
          <img
            className="sm-wide narrow"
            src={wastage}
            alt="Before: one electricity bill. After: a machine-wise breakdown that shows wastage"
            loading="lazy"
          />
          <ul className="sm-benefits">
            {benefits.items.map((b) => (
              <li key={b.text}>
                <span className="sm-ico">
                  <BenefitIcon name={b.icon} />
                </span>
                <span>
                  {b.text} {b.soon && <Soon />}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="sm-section" id="about" aria-labelledby="about-h">
          <h2 id="about-h">{founders.title}</h2>
          <p className="sm-sub strong">{founders.tagline}</p>
          <div className="sm-prose">
            {founders.paragraphs.map((p) => (
              <p key={p}>{p}</p>
            ))}
            <blockquote>{founders.philosophy}</blockquote>
            <p>{founders.closing}</p>
          </div>
        </section>

        <section
          className="sm-section sm-contact"
          id="contact"
          aria-labelledby="contact-h"
        >
          <div>
            <h2 id="contact-h">{connect.title}</h2>
            <p className="sm-sub">{connect.text}</p>
            <ul className="sm-details">
              <li>{company.address}</li>
              <li>
                <a href={`tel:${company.phone.replace(/[^\d+]/g, "")}`}>
                  {company.phone}
                </a>
              </li>
              <li>
                <a href={`mailto:${company.email}`}>{company.email}</a>
              </li>
            </ul>
            {wa && (
              <a
                className="sm-btn ghost"
                href={wa}
                target="_blank"
                rel="noopener noreferrer"
              >
                Chat on WhatsApp
              </a>
            )}
          </div>
          <ContactForm />
        </section>
      </main>

      <footer className="sm-foot">
        <span>© {new Date().getFullYear()} ricemillmart.com</span>
        <Link to="/login">Plant owner login</Link>
      </footer>
    </div>
  );
}
