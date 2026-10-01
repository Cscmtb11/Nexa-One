# Foundation Architecture

Browser → Cloudflare → Web/API → tenant context + RBAC → module service → database/workflow → audit

AI disabled:
application → normal service path

AI enabled:
application → AI policy/quota check → ai.springnexa.in → approved provider

Every tenant-scoped query must enforce organisation context.
