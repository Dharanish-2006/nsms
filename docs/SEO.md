# SEO

- Only `https://ricemillmart.com/` is indexable. It shows the public landing page to signed-out visitors.
- Login, register, the owner app and `/admin` are `noindex` (meta tag set per route in `src/lib/seo.js`, plus an `X-Robots-Tag` header from `deploy/nginx.conf`).
- Unknown URLs return a real HTTP 404.
- `public/robots.txt`, `public/sitemap.xml`, `public/site.webmanifest` and `public/og-image.png` are served from the site root.
- Structured data (Organization, WebSite, SoftwareApplication) is in `index.html`. Add address, phone and email to it only once they are real.
- Company contact details come from `COMPANY_ADDRESS`, `COMPANY_PHONE`, `COMPANY_EMAIL` in `deploy/prod.env`. Empty values are hidden from the public page.

## After each deploy

1. Google Search Console: add `ricemillmart.com` as a Domain property (DNS TXT record in GoDaddy), then submit `https://ricemillmart.com/sitemap.xml` and request indexing of `/`.
2. Bing Webmaster Tools: import the site from Search Console.
3. Check `curl -sI https://ricemillmart.com/nothing-here` returns 404 and `curl -sI https://ricemillmart.com/login` has `X-Robots-Tag: noindex`.
