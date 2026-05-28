/**
 * UK Deals Scanner — click-tracking redirect Worker.
 *
 * Deploys free on Cloudflare Workers. Routes outbound deal links through
 * /go?u=<encoded target>&c=<category>, increments a counter in Workers KV,
 * then 302-redirects to the target. Lets you measure clicks per category
 * before monetising — without exposing any user data.
 *
 * SETUP (see SETUP.md step 6):
 *   1. Create a KV namespace, bind it as CLICKS.
 *   2. wrangler deploy.
 *   3. Put the deployed URL in config.yaml -> click_tracking.worker_base_url
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Simple stats endpoint: /stats?c=tech
    if (url.pathname === "/stats") {
      const cat = url.searchParams.get("c") || "all";
      const total = (await env.CLICKS.get(`clicks:${cat}`)) || "0";
      return new Response(JSON.stringify({ category: cat, clicks: Number(total) }), {
        headers: { "content-type": "application/json" },
      });
    }

    if (url.pathname === "/go") {
      const target = url.searchParams.get("u");
      const category = url.searchParams.get("c") || "unknown";

      if (!target || !/^https?:\/\//i.test(target)) {
        return new Response("Bad request", { status: 400 });
      }

      // Increment counters without blocking the redirect.
      const bump = async (key) => {
        const cur = Number((await env.CLICKS.get(key)) || "0");
        await env.CLICKS.put(key, String(cur + 1));
      };
      // ctx.waitUntil keeps the redirect instant; fall back if absent.
      try {
        await Promise.all([bump(`clicks:${category}`), bump("clicks:all")]);
      } catch (_) { /* never block redirect on a counter error */ }

      return Response.redirect(target, 302);
    }

    return new Response("UK Deals Scanner redirect worker", { status: 200 });
  },
};
