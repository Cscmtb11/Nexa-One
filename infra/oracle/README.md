# Oracle Cloud Production

NEXA targets a single Oracle Cloud Linux VM for the initial low-cost deployment. The application is containerised and uses PostgreSQL 16 with a persistent Docker volume.

## Prerequisites

- An Oracle Compute VM with Docker Engine and the Docker Compose plugin installed.
- DNS for the app and API hostnames proxied through Cloudflare.
- A Cloudflare Tunnel or hardened reverse proxy on the VM.
- A strong database password and JWT signing secret.
- SSH access restricted to trusted administrator IPs.

Oracle Always Free capacity is subject to regional availability, account eligibility and provider limits. Do not assume a VM shape will always be available or that the free allowance is a production SLA.

## First deployment

1. Clone the repository on the VM.
2. Copy `infra/oracle/.env.production.example` to `infra/oracle/.env.production`.
3. Replace every placeholder with unique random secrets. Prefer URL-safe hexadecimal secrets (for example, `openssl rand -hex 32`) because the database URL is assembled from environment variables.
4. From the repository root, run:

   ```bash
   docker compose --env-file infra/oracle/.env.production -f infra/oracle/docker-compose.production.yml up -d --build
   ```

5. Confirm the API health endpoint locally:

   ```bash
   curl --fail http://127.0.0.1:8000/health
   ```

6. Route `app.springnexa.in` to `http://localhost:3000` and `api.springnexa.in` to `http://localhost:8000` using Cloudflare Tunnel ingress rules.
7. Verify TLS, CORS, login, tenant switching, migration status and backups before onboarding real organisations.

## Operations

- Database is not published on a host port.
- Web and API bind to loopback only; expose them through Cloudflare Tunnel/reverse proxy.
- Alembic migrations execute before the API process starts.
- Persist PostgreSQL data in the `nexa_pg` volume.
- Schedule encrypted off-VM database backups and periodically test restoration.
- Keep Docker images updated and review security advisories.
- Configure Oracle security lists and host firewall to expose only required ingress (normally SSH from trusted IPs and tunnel egress).

## Important limitations

This is an initial single-VM deployment profile, not high availability. The VM, database volume and application share one failure domain. Before production healthcare data is loaded, implement off-site backups, restore drills, monitoring, MFA, incident response, access reviews and applicable privacy/security compliance controls.
