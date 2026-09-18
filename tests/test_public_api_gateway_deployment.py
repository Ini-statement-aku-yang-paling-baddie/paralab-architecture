"""Deployment contract for the single-origin public ParaLab API."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicApiGatewayDeploymentTests(unittest.TestCase):
    def test_production_assets_route_only_the_public_api_prefixes(self):
        compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
        nginx = (ROOT / "deploy" / "nginx" / "paralab-api.conf").read_text(encoding="utf-8")

        self.assertIn("reverse-proxy:", compose)
        self.assertIn("model-gateway:", compose)
        self.assertIn("f3-api:", compose)
        self.assertIn(":/models/sentence-transformer:ro", compose)
        self.assertIn("location ^~ /v1/f3/", nginx)
        self.assertIn("proxy_pass http://f3-api:7860;", nginx)
        for feature in ("f1", "f2", "f4", "f5"):
            self.assertIn(f"location ^~ /v1/{feature}/", nginx)
        self.assertIn("return 404;", nginx)

    def test_cloudflare_tunnel_overlay_has_no_host_ports_or_tls_files(self):
        overlay = (ROOT / "docker-compose.cloudflare-tunnel.yml").read_text(encoding="utf-8")
        nginx = (ROOT / "deploy" / "nginx" / "paralab-api.cloudflare-tunnel.conf").read_text(encoding="utf-8")
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("ports: !reset []", overlay)
        self.assertIn('"8080"', overlay)
        self.assertIn("cloudflared:", overlay)
        self.assertIn("tunnel --no-autoupdate run --token ${TUNNEL_TOKEN", overlay)
        self.assertIn("read_only: true", overlay)
        self.assertIn("cap_drop:", overlay)
        self.assertIn("- ALL", overlay)
        self.assertIn("listen 8080 default_server;", nginx)
        self.assertNotIn("ssl_certificate", nginx)
        self.assertIn("$http_cf_connecting_ip", nginx)
        for feature in ("f1", "f2", "f3", "f4", "f5"):
            self.assertIn(f"location ^~ /v1/{feature}/", nginx)
        self.assertIn(".env.cloudflare-tunnel", ignored)

    def test_assets_keep_model_weights_out_of_images_and_configure_cors(self):
        dockerfile = (ROOT / "deploy" / "model-gateway.Dockerfile").read_text(encoding="utf-8")
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.production.example").read_text(encoding="utf-8")

        self.assertIn("models/", dockerignore)
        self.assertNotIn("COPY models/", dockerfile)
        self.assertIn("PARALAB_CORS_ORIGINS=https://app.example.com", env_example)
        self.assertIn("PUBLIC_API_PORT=443", env_example)


if __name__ == "__main__":
    unittest.main()
