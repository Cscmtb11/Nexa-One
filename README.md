# Nexa Management

SpringNexa Private Limited's multi-organisation, multi-tenant healthcare management platform.

## Core modules
- PMS — Patient Management System
- HMS — Hospital Management System
- LMIS — Laboratory Management Information System
- TMS — configurable transaction / treatment management
- Billing, Inventory, HR and Analytics
- Workflow + automation engine
- Optional AI gateway at ai.springnexa.in

AI is OFF by default. Core workflows must operate without AI.

## Target architecture
Cloudflare → Nexa Web/API → tenant-aware services → database/workflow/audit
Oracle Cloud is the production infrastructure target.
GitHub is the source-control and CI/CD system.

## Local development
cp .env.example .env
docker compose up --build

API: http://localhost:8000
Web: http://localhost:3000
