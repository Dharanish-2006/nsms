import { useEffect } from "react";

export const SITE_URL = "https://ricemillmart.com";

const setMeta = (selector, attr, key, value) => {
  let el = document.head.querySelector(selector);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", value);
};

const setCanonical = (href) => {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
};

export function useSeo({ title, description, path = "/", index = false }) {
  useEffect(() => {
    document.title = title;
    if (description) {
      setMeta('meta[name="description"]', "name", "description", description);
      setMeta('meta[property="og:description"]', "property", "og:description", description);
    }
    setMeta('meta[property="og:title"]', "property", "og:title", title);
    setMeta(
      'meta[name="robots"]',
      "name",
      "robots",
      index ? "index, follow, max-image-preview:large" : "noindex, nofollow",
    );
    setCanonical(SITE_URL + path);
  }, [title, description, path, index]);
}
