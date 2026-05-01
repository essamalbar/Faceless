// Cloudflare Worker — proxy fetch for blocked CDN downloads.
//
// Usage:  GET https://<your-worker>.workers.dev/?url=<encoded URL>&k=<secret>
//
// Forwards the request to the target URL using Cloudflare's edge network
// (which is not subject to ISP-level SNI blocks) and streams the response back.
//
// Env binding (set in worker dashboard → Settings → Variables):
//   PROXY_SECRET   shared secret required in the `k` query param.
//                  Prevents random people from using your worker as a generic proxy.
//
// Free tier: 100,000 requests/day, more than enough for ~10 videos × 4 clips/day.

export default {
  async fetch(request, env, ctx) {
    const inUrl = new URL(request.url);
    const target = inUrl.searchParams.get("url");
    const secret = inUrl.searchParams.get("k") || "";

    if (!target) {
      return new Response("missing ?url=<target-url>", { status: 400 });
    }

    if (env.PROXY_SECRET && secret !== env.PROXY_SECRET) {
      return new Response("forbidden", { status: 403 });
    }

    let targetUrl;
    try {
      targetUrl = new URL(target);
    } catch (_e) {
      return new Response("bad url", { status: 400 });
    }

    // Allowlist hostnames that this proxy is permitted to fetch.
    // Add others if Kie.ai uses different CDNs over time.
    const allowed = [
      "tempfile.aiquickdraw.com",
      "kie.ai",
      "api.kie.ai",
      "cdn.kie.ai",
    ];
    if (!allowed.some(h => targetUrl.hostname === h || targetUrl.hostname.endsWith("." + h))) {
      return new Response(`hostname not allowed: ${targetUrl.hostname}`, { status: 403 });
    }

    const upstream = await fetch(targetUrl.toString(), {
      method: "GET",
      headers: {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "*/*",
      },
      redirect: "follow",
    });

    // Stream the body straight back; preserve content-type + length when present.
    const headers = new Headers();
    const passthrough = ["content-type", "content-length", "content-disposition", "etag"];
    for (const h of passthrough) {
      const v = upstream.headers.get(h);
      if (v) headers.set(h, v);
    }
    if (!headers.has("content-type")) headers.set("content-type", "video/mp4");

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  },
};
