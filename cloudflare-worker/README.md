# CDN Proxy Worker

A tiny Cloudflare Worker that proxies Kie.ai CDN downloads. Use when your ISP / firewall blocks the CDN host directly (common for users in regions with Chinese-AI-CDN restrictions).

## Why

Kie.ai serves generated videos from `tempfile.aiquickdraw.com` (Cloudflare-fronted CDN). Some networks (UAE, Saudi, China, etc.) reset connections to that hostname at the SNI level. The pipeline's downloads then fail with `Connection reset by peer` regardless of the HTTP client used.

A Cloudflare Worker runs inside Cloudflare's network, so it can fetch the CDN, then re-serve the bytes to your machine — and your machine can talk to `<your-worker>.workers.dev` even when it can't talk to `tempfile.aiquickdraw.com`.

**Cost:** Cloudflare Workers free tier = 100,000 requests/day. One video = 4 download requests. Way under the limit.

## Deploy in 5 minutes

1. **Sign up at https://dash.cloudflare.com/sign-up** (free; just an email + password).
2. In the dashboard sidebar, click **Workers & Pages**.
3. Click **Create application** → **Create Worker**.
4. Name it whatever you like — e.g. `faceless-kie-proxy`. Click **Deploy** to create the default worker.
5. Click **Edit code**.
6. **Replace the entire contents** with the code in [`worker.js`](./worker.js) (the file in this folder). Click **Deploy**.
7. **Set the secret** (prevents random strangers from using your worker):
   - Click **Settings** → **Variables and Secrets** → **Add variable**.
   - Type: **Secret**.
   - Name: `PROXY_SECRET`.
   - Value: any random string you want (~20 chars). Save it — you'll add it to `.env` next.
   - Click **Deploy**.
8. Copy the worker URL from the top of the dashboard. It looks like:
   ```
   https://faceless-kie-proxy.<your-username>.workers.dev
   ```

## Wire it into the pipeline

Add two lines to `/Users/gileshannah/Desktop/faceless/.env`:

```bash
export KIE_DOWNLOAD_PROXY=https://faceless-kie-proxy.<your-username>.workers.dev
export KIE_DOWNLOAD_PROXY_SECRET=<the secret you just set>
```

Then re-run:

```bash
source .env
uv run python run.py --shorts --resume out/2026-05-01-2147 --theme folkloric --seed "بئر قديم في قرية مهجورة"
```

The `_download` method now routes via the Worker only when `KIE_DOWNLOAD_PROXY` is set — so no impact on any other code path.

## Sanity test (optional)

After deploying, test directly:

```bash
curl -o /tmp/test.png "https://faceless-kie-proxy.<your-username>.workers.dev/?url=https%3A%2F%2Fcdn.kie.ai%2Ffoo.png&k=<your-secret>"
```

If you get a real PNG (or whatever you proxy), the worker is working.
