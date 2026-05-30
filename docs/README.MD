# YourDealsUK Website

A single-file landing page (`index.html`) for your deals brand. Purpose:
1. Give Awin (and other affiliate networks) a real site to approve.
2. Be the public front door for your Telegram channel.

No build step, no dependencies — it's one HTML file.

## Before deploying — edit two things

1. **Telegram link.** Find `REPLACE_WITH_YOUR_TELEGRAM_LINK` and replace with
   your channel invite link (e.g. `https://t.me/yourchannel`).
2. **Brand name (optional).** It's called "YourDealsUK" throughout — find/replace
   if you want a different name.

## Deploy free — Cloudflare Pages (recommended)

1. Go to dash.cloudflare.com → Workers & Pages → Create → Pages.
2. Connect your GitHub repo → select `uk-deals-scanner`.
3. Build settings:
   - Framework preset: **None**
   - Build command: *(leave blank)*
   - Build output directory: **website**
4. Deploy. You get a free `*.pages.dev` URL instantly.

## Or — GitHub Pages

1. Repo → Settings → Pages.
2. Source: Deploy from branch → `main` → folder `/website` won't work directly
   (Pages serves `/` or `/docs`). Easiest: move `index.html` to a `/docs` folder
   and select `/docs`, OR use Cloudflare Pages above (handles `/website` fine).

## Custom domain (~£8–12/yr, optional but helps approval)

A real domain (e.g. `yourdealsuk.co.uk`) makes affiliate approval far more likely
than a `.pages.dev` subdomain.
- Buy from Cloudflare Registrar (at-cost) or Namecheap.
- In Cloudflare Pages → Custom domains → add it. DNS auto-configures if bought
  at Cloudflare.

## For Awin approval

When applying, point them at your live URL. Having the site show:
- what the service is, ✓ (done)
- how it works, ✓ (done)
- an affiliate disclosure, ✓ (in footer)
- a working Telegram link ✓ (once you edit it)

...covers the usual approval checklist. Some advertisers still review manually;
that's normal.
