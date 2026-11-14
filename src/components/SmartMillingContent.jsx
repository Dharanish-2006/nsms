import { useState } from "react";
import { api } from "../api";
import { USE_MOCK } from "../config";
import { benefits, connect, founders, intelligence } from "../content/smartMilling";
import energy from "../assets/images/sm-energy.svg";
import maintenance from "../assets/images/sm-maintenance.svg";
import production from "../assets/images/sm-production.svg";
import "./smartmilling.css";

const PICTURES = { production, energy, maintenance };

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
          ? "Demo mode: saved in this browser only, not sent."
          : "Thank you. Our team will get in touch with you.",
      });
    } catch (err) {
      setState({
        phase: "error",
        message: err?.message || "Could not send. Please try again.",
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
          <input
            tabIndex={-1}
            autoComplete="off"
            value={form.website}
            onChange={set("website")}
          />
        </label>
      </div>
      <button className="sm-btn" type="submit" disabled={!ready}>
        Submit
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

/** Everything below the sign-in area on the login page. Text lives in src/content/smartMilling.js. */
export default function SmartMillingContent() {
  return (
    <div className="sm">
      <section className="sm-section" aria-label="Intelligence">
        <div className="sm-cards">
          {intelligence.map((c) => (
            <article className="sm-card" key={c.key}>
              <img src={PICTURES[c.key]} alt="" loading="lazy" />
              <h2>{c.title}</h2>
              <p>{c.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="sm-section sm-band" aria-labelledby="ben-h">
        <h2 id="ben-h">{benefits.title}</h2>
        <ul className="sm-benefits">
          {benefits.items.map((b) => (
            <li key={b.text}>
              <span className="sm-ico">
                <BenefitIcon name={b.icon} />
              </span>
              <span>{b.text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="sm-section" aria-labelledby="about-h">
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

      <section className="sm-section sm-contact" aria-labelledby="contact-h">
        <div>
          <h2 id="contact-h">{connect.title}</h2>
          <p className="sm-sub">{connect.text}</p>
        </div>
        <ContactForm />
      </section>
    </div>
  );
}
