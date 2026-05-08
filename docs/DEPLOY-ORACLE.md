# Deploy to Oracle Cloud Always-Free

Production deployment recipe for the faceless backend on an Oracle Always-Free ARM64 VM. Total setup time: ~30 minutes once your Oracle VM is provisioned.

## Prerequisites

- Oracle Cloud account verified (signup at https://www.oracle.com/cloud/free/ — credit card required, never charged on Always-Free)
- A provisioned `VM.Standard.A1.Flex` instance with **4 OCPUs + 24 GB RAM**, Ubuntu 22.04 Minimal
- SSH access: `ssh ubuntu@<public-ip>`
- A registered domain you control (e.g. via Cloudflare Registrar, ~$10/year)
- A Cloudflare account (free) with your domain added

## Architecture overview

```
Flutter app (iOS/Android/web)
        │  HTTPS
        ▼
Cloudflare Tunnel  ←─── cloudflared container (in compose)
        │  http://api:8000  (internal Docker network)
        ▼
  faceless API container  ─── writes to /app/out (bind-mounted to ~/faceless/out/)
        │  subprocess
        ▼
  run.py → Anthropic / Kie.ai / ElevenLabs  (outbound HTTPS)
```

The Oracle VM never exposes port 8000 to the internet — all inbound traffic arrives through the Cloudflare Tunnel.

## Step 1 — Provision the Oracle VM

1. Log in to https://cloud.oracle.com/
2. Compute → Instances → Create Instance
3. Shape: **VM.Standard.A1.Flex**, 4 OCPUs, 24 GB RAM (all Always-Free)
4. Image: **Ubuntu 22.04 Minimal** (ARM64)
5. Networking: default VCN is fine; ensure a public IP is assigned
6. SSH key: paste your public key (or generate one)
7. Create — takes ~2 minutes

Note your instance's **public IP address**.

## Step 2 — One-time VM setup

SSH in and run:

```bash
# Update packages
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker (official Docker Engine, not the Ubuntu snap)
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin git

# Allow non-root Docker (log out and back in after this)
sudo usermod -aG docker ubuntu
```

Log out and back in, then verify: `docker run --rm hello-world`

### Open Oracle's firewall (Security List)

Oracle Cloud adds its own firewall on top of the VM's iptables. You need to open port 443 (HTTPS) for inbound tunnel traffic from Cloudflare. The API itself (8000) does NOT need to be open — traffic arrives via the tunnel.

In the Oracle Cloud console:
1. Networking → Virtual Cloud Networks → your VCN → Security Lists → Default
2. Add Ingress Rule: Source CIDR `0.0.0.0/0`, Protocol TCP, Destination Port `443`
3. Save

The VM's own iptables are typically open by default on Oracle Ubuntu — if not:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## Step 3 — Cloudflare Tunnel (named, recommended)

Named tunnels give you a stable `https://api.yourdomain.com` URL that survives VM restarts and container rebuilds.

1. Go to https://one.dash.cloudflare.com → Networks → Tunnels → **Create a tunnel**
2. Connector type: **Docker**
3. Name: `faceless-prod`
4. Copy the `docker run` command shown — extract the **token** from `--token <TOKEN>`
5. Under **Public Hostnames**, click Add:
   - Subdomain: `api`
   - Domain: `yourdomain.com`
   - Service Type: `HTTP`
   - URL: `api:8000`
6. Save

You now have a `CLOUDFLARE_TUNNEL_TOKEN` value to put in `.env`.

### Ephemeral tunnel (quick test, no domain needed)

If you just want to test without setting up a domain, edit `docker-compose.prod.yml` and change the `cloudflared` command to:

```yaml
command: tunnel --no-autoupdate --url http://api:8000
```

Remove `CLOUDFLARE_TUNNEL_TOKEN` from `.env`. The URL changes on every restart — not suitable for production but handy for a smoke test.

## Step 4 — Deploy the app

On the Oracle VM:

```bash
# Clone the repo
git clone https://github.com/<your-user>/faceless.git
cd faceless

# Create .env with your secrets
cat > .env << 'EOF'
FACELESS_API_TOKEN=<run: openssl rand -hex 32>
ANTHROPIC_API_KEY=sk-ant-...
KIE_API_KEY=...
ELEVENLABS_API_KEY=...
CLOUDFLARE_TUNNEL_TOKEN=...
EOF
chmod 600 .env   # readable only by ubuntu user

# Build and start with the prod overlay
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Follow logs (Ctrl-C to stop following, containers keep running)
docker compose logs -f
```

Wait ~60 seconds for the API healthcheck to pass, then verify from your laptop:

```bash
curl https://api.yourdomain.com/healthz
# Expected: {"ok":true}
```

## Step 5 — Point the Flutter app at the new URL

In the Flutter app's Settings screen, set:
- API URL: `https://api.yourdomain.com`
- Token: the value of `FACELESS_API_TOKEN` from your `.env`

Or if using `scripts/run-app.sh` locally with the remote backend:

```bash
# In .env on your Mac:
export FACELESS_API_URL=https://api.yourdomain.com
```

## Maintenance

### Check status

```bash
docker compose ps
docker compose logs api --tail 50
docker compose logs cloudflared --tail 20
```

### Update the app

```bash
cd ~/faceless
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The old container is replaced in-place. Running pipeline jobs survive if they are far enough along (artifacts on disk); jobs in the "creating" state will fail and need Resume.

### Rollback

```bash
git checkout <previous-commit-sha>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Auto-restart on VM reboot

`restart: unless-stopped` in the compose file means Docker automatically restarts the containers when the VM reboots. No systemd unit needed.

### Resource monitoring

```bash
docker stats --no-stream        # one-shot CPU + memory snapshot
df -h /                         # disk usage — out/ grows fast
du -sh ~/faceless/out/          # how much the pipeline has written
```

### Clean up old runs

The `out/<run-id>/` directories are not auto-deleted. After several weeks they can fill the 50 GB boot volume:

```bash
# List runs older than 30 days (dry-run)
find ~/faceless/out -maxdepth 1 -type d -mtime +30

# Delete them
find ~/faceless/out -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

A future B-stage will move completed artifacts to Cloudflare R2 to avoid this entirely.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `curl healthz` times out | Oracle Security List blocks port 443 | Add ingress rule for TCP 443 |
| Cloudflare tunnel shows "Offline" | Wrong token or API not healthy yet | Check `docker compose logs cloudflared` |
| API container crashes on start | Missing env var | Check `.env` has all required keys |
| `uv sync` fails during build | ARM64 wheel missing for a dep | Pin an older version or use `--no-binary` |
| Whisper download slow on first run | Expected — model is ~150 MB | Let it finish; subsequent runs skip download |
| `out/` fills disk | Many runs accumulate | Run the cleanup command above |
