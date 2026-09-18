# Production: one HTTPS public API origin

`docker-compose.production.yml` exposes one origin for the ParaLab website. Only the reverse proxy publishes host ports; F3 and the model gateway live on the internal `backend` network.

| Public path | Internal target |
|---|---|
| `/v1/f3/*` | `f3-api:7860` |
| `/v1/f1/*`, `/v1/f2/*`, `/v1/f4/*`, `/v1/f5/*` | `model-gateway:8100` |

Everything else returns `404`. HTTP port 80 only redirects to HTTPS; use `https://api.example.com` as the website's API base URL. The `F4` endpoint served here is the model-gateway endpoint, not the legacy F3 adapter route.

## Prerequisites

1. Build/run on a host with Docker Engine plus the Compose plugin. The Cloudflare overlay uses Compose's `!reset`/`!override` tags, so use Compose v2.24.4 or newer (`docker compose version`).
2. Terminate TLS in this stack and obtain a certificate/key for the API hostname. Keep the private key readable only by the deployment account; do not commit it.
3. Stage ignored F1 artifacts on the host in one directory, defaulting to `models/sentence-transformer/`:

   ```text
   models/sentence-transformer/
   ├── embeddings_paralab.npy
   ├── embedding_model/
   ├── Qwen2.5-1.5B-Instruct/
   └── formulab-qwen-lora/
   ```

   These are runtime volume contents, not image layers and not Git artifacts. The source repository's older local layout can be copied/reorganized into this deployment directory without changing model code.

## Configure and start

```bash
cp .env.production.example .env.production
# Edit the website origin, TLS file paths, model directory, and (if needed) port.
docker compose --env-file .env.production -f docker-compose.production.yml config
docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
```

Set `PARALAB_CORS_ORIGINS` to the exact public website origin, for example `https://app.example.com`. Multiple exact origins may be comma-separated. Do not use `*`: the APIs are intended for a known browser client and do not need credentialed CORS.

The current `paralab-website` environment contract is `VITE_PARALAB_F3_URL`, not `VITE_PARALAB_API_URL`. Set `VITE_PARALAB_F3_URL=https://api.example.com` when building the website; its F3 client appends its documented `/v1/f3/...` path. Do not expose service ports `7860` or `8100` through a host firewall or another proxy.

## Free public path: Cloudflare Pages + Cloudflare Tunnel

Use this option when the website is deployed to Cloudflare Pages and the API stays on this laptop. It is an overlay on the TLS/VPS stack above, not a replacement for it: `docker-compose.production.yml` remains the direct HTTPS deployment, while `docker-compose.cloudflare-tunnel.yml` removes its host port bindings and swaps in an internal plaintext Nginx listener. Cloudflare terminates the public TLS connection; `cloudflared` is the only service that can reach Nginx over Docker's `edge` network.

### Safe setup

1. In Cloudflare Zero Trust, create a **named** tunnel (not a Quick Tunnel). Copy the Docker token shown by the dashboard. The token is a connector credential, so do not put it in a shell history, Pages variable, Git, issue, or chat transcript.
2. Create a public hostname for the API, such as `api.example.com`. Set its service type to **HTTP** and its URL exactly to `http://reverse-proxy:8080`. Cloudflare associates this hostname with the named tunnel; do not create a public DNS A/AAAA record to the laptop.
3. Configure the Pages project's production environment variable `VITE_PARALAB_F3_URL=https://api.example.com`, then redeploy the Pages site. Set `PARALAB_CORS_ORIGINS` in `.env.production` to the exact Pages/custom-site origin, for example `https://app.example.pages.dev`.
4. Keep the production settings and tunnel token in separate untracked files:

   ```bash
   cp .env.production.example .env.production
   cp .env.cloudflare-tunnel.example .env.cloudflare-tunnel
   chmod 600 .env.production .env.cloudflare-tunnel
   # Edit both files. Do not add TLS_CERT_PATH/TLS_KEY_PATH for this overlay.
   ```

5. Render and start the combined stack. This publishes **no** host ports, including port 80/443/8080:

   ```bash
   docker compose --env-file .env.production --env-file .env.cloudflare-tunnel \
     -f docker-compose.production.yml -f docker-compose.cloudflare-tunnel.yml config
   docker compose --env-file .env.production --env-file .env.cloudflare-tunnel \
     -f docker-compose.production.yml -f docker-compose.cloudflare-tunnel.yml up --build -d
   ```

`cloudflared` runs `tunnel --no-autoupdate run --token ...` with a read-only filesystem and no Linux capabilities. Rotate/revoke the tunnel token in Zero Trust if it is exposed, update the local untracked file, and recreate only the connector.

### Verify the public path

First confirm Docker did not publish a listening port and that the connector is healthy/running:

```bash
docker compose --env-file .env.production --env-file .env.cloudflare-tunnel \
  -f docker-compose.production.yml -f docker-compose.cloudflare-tunnel.yml ps
docker compose --env-file .env.production --env-file .env.cloudflare-tunnel \
  -f docker-compose.production.yml -f docker-compose.cloudflare-tunnel.yml port reverse-proxy 8080
```

The second command must print nothing and return non-zero because `8080` is not a host-published port. Then, from a machine outside the Docker host, verify Cloudflare TLS, routing, and CORS without bypassing certificate validation:

```bash
curl -i https://api.example.com/not-a-route
curl -i -X OPTIONS https://api.example.com/v1/f2/health-check \
  -H 'Origin: https://app.example.pages.dev' \
  -H 'Access-Control-Request-Method: POST'
```

Expect `404` for the first request and `access-control-allow-origin: https://app.example.pages.dev` on the preflight. Also inspect `cloudflared` logs and the tunnel's connector status in Zero Trust. If the hostname is reachable while the `cloudflared` container is stopped, the hostname is routed somewhere else and this deployment has not been verified.

### Limits of this free path

The public API is available only while this laptop, Docker, its network, and the `cloudflared` connector are running. Sleep, reboot, power loss, changing networks, or Cloudflare account/tunnel issues take it offline. It is unsuitable for an availability commitment or sensitive/regulated workloads. This repository still has **no application authentication**: a public tunnel makes these API paths public. Cloudflare rate limiting and WAF can reduce abuse, but use Cloudflare Access or add application authentication before granting private/restricted access.

## Health and rollout behavior

The healthchecks are deliberately different:

- **F3** checks `GET /health`, which loads/verifies the serialized artifact. A missing artifact, bad hash, or runtime-version mismatch returns `503` and prevents `reverse-proxy` startup.
- **Model gateway** checks `GET /health`, which verifies the HTTP process and deterministic F2/F4/F5 availability. F1 weights are lazy-loaded at the first `/v1/f1/query`; a missing/incompatible model volume causes that request to return `503`, not a misleading successful F1 response.
- **Reverse proxy** runs `nginx -t`; it starts only after both upstream healthchecks are healthy. Internal health endpoints are not publicly routed.

Inspect deployment state with:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=100 reverse-proxy f3-api model-gateway
```

After DNS points to the host, verify HTTPS and CORS from an allowed origin:

```bash
curl -i https://api.example.com/not-a-route
curl -i -X OPTIONS https://api.example.com/v1/f2/health-check \
  -H 'Origin: https://app.example.com' \
  -H 'Access-Control-Request-Method: POST'
```

The first command must be `404`; the preflight must contain `access-control-allow-origin: https://app.example.com`. Do not use `curl -k` in production: certificate validation is part of the check.

## Security defaults and operations

- Containers use read-only root filesystems, dropped Linux capabilities, no-new-privileges, and internal-only backend networking.
- The reverse proxy accepts HTTPS only for API calls, applies request-size/time limits and per-IP rate limits, does not expose API documentation or health paths, and sends basic security headers.
- The model container sets Hugging Face/Transformers offline mode so it cannot silently download another model at runtime.
- There is no application authentication in this repository. Rate limits reduce accidental abuse but are not authorization. Put an identity-aware edge/WAF in front of the API if the service needs restricted access.
- Rotate certificates through the host's certificate process, then run `docker compose ... up -d --force-recreate reverse-proxy`. Keep `.env.production`, TLS keys, and model artifacts out of source control.
