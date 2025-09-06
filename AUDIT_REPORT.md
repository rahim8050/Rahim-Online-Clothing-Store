1. Executive Summary (Production Readiness Score, top risks)

- Production Readiness Score: 62/100
- Top Risks:
  - Secrets present in repository (.env checked-in). Rotate immediately and purge from history.
  - Channels misconfiguration would force InMemory layer in prod, breaking WebSockets at scale.
  - Duplicate/conflicting settings (DEBUG, TIME_ZONE, ALLOWED_HOSTS) create non-deterministic behavior.
  - Dual payment models (orders.Transaction vs payments.Transaction) increase risk in webhooks/reconciliation.
  - Missing readiness probe; only liveness existed.

2. Architecture & Environments

- Backend: Django 5, DRF, Channels via Daphne/Uvicorn. Redis required in prod.
- Frontend: Tailwind v4 + Vite + Vue 3 ChatPanel (teleport to body; pointer-events safe).
- DB: MySQL locally via DATABASE_URL; Postgres supported via dj-database-url. MySQL tz-tables bypassed by time_zone='+00:00'.
- Cache: Redis optional for Django cache; Channels must use Redis in prod.
- Hosting: Render (staging) + DigitalOcean (prod).
- Health: /healthz present; /readyz added in this patch.

3. Critical Findings (P0/P1) with file/line, diffs, tests

- P0: Channels layer forced to InMemory in prod
  - File: Rahim_Online_ClothesStore/settings.py:208
  - Problem: CHANNEL_LAYERS reset to InMemory unconditionally, overriding the proper Redis config at 173.
  - Fix (applied): remove override; make Redis conditional on REDIS_URL.
  - Minimal diff: patches/0001-fix-channels-layer.diff
  - Tests: tests_added/test_settings_channel_layer.py
  - Verify: set REDIS_URL and run python manage.py check; run pytest -q tests_added/test_settings_channel_layer.py

- P0: Repository contains real secrets (.env)
  - File: .env (do not print values)
  - Impact: Credential leakage risk; may have been committed to history.
  - Fix: Ensure .env is gitignored (already). Purge from git history (git filter-repo), rotate PAYSTACK/STRIPE/PAYPAL/EMAIL secrets, and move to environment variables in Render/DO.
  - Verify: git ls-files | rg "^\.env$" should return empty; secrets stored only in hosting env.

- P1: Conflicting settings cause non-deterministic config
  - File: Rahim_Online_ClothesStore/settings.py:249 (TIME_ZONE = "UTC"), 285 (DEBUG reassign), 305 (ALLOWED_HOSTS reset)
  - Problem: Later block overrides earlier ENV-driven values; TIME_ZONE contradicts Africa/Nairobi requirement.
  - Fix (applied): stop reassigning DEBUG, keep TIME_ZONE=Africa/Nairobi, guard ALLOWED_HOSTS default only when empty.
  - Minimal diff: patches/0002-sanitize-settings-duplicates.diff
  - Verify: python - <<<'import os;os.environ["ENV"]="prod";import Rahim_Online_ClothesStore.settings as s;print(s.DEBUG,s.TIME_ZONE,s.ALLOWED_HOSTS)'

- P1: Readiness probe missing
  - Files: core/views.py: add readyz; Rahim_Online_ClothesStore/urls.py: add path
  - Fix (applied): lightweight DB SELECT 1 readiness endpoint.
  - Verify: uvicorn …; curl -i /readyz returns 200 and {"status":"ready"} when DB reachable.

- P1: Checkout submit potentially intercepted by chat panel
  - File: src/components/ChatPanel.vue:94
  - Problem: Send button inside a form lacked type=button; conservative hardening avoids any cross-form submit.
  - Fix (applied): add type="button" and @click.stop.prevent.
  - Minimal diff: patches/0003-chatpanel-send-button.diff
  - Verify: On order_create page, selecting address enables submit; pressing Enter inside assistant does not submit checkout.

- P1: Dual payment models and webhook stacks
  - Files:
    - payments/models.py (canonical Transaction) vs orders/models.py:401+ (legacy Transaction/PaymentEvent)
    - payments/views.py webhooks vs orders/views.py:741 paystack_webhook
  - Impact: Inconsistent state, two sources of truth, test flakiness, reconciliation drift.
  - Fix (plan): Migrate to payments.Transaction across codebase. Deprecate orders.Transaction/PaymentEvent.
  - Minimal next step diff: create alias models or update import sites (users/views.py, tests) to payments.Transaction; add data migration to copy records.
  - Tests present: payments/tests/test_payments.py; add more webhook replay tests.

- P1: MySQL dev environment failing on mysqlclient
  - Symptom: manage.py check fails if DATABASE_URL points to MySQL but mysqlclient not installed.
  - Fix: Install mysqlclient on dev or set DATABASE_URL=sqlite:///db.sqlite3 for local checks. In CI, run Postgres via dj-database-url.
  - Verify: python manage.py check --deploy after pip install -r requirements.txt

4. Production Gaps Table

| Gap | Impact | Fix Steps | Owner | ETA |
| --- | --- | --- | --- | --- |
| Secrets in repo | Credential exposure | Remove .env from history; rotate keys; use env vars on hosts | Security | 2h + rotations |
| Channels InMemory in prod | WebSockets fail under concurrency | Use Redis via REDIS_URL; remove override (done) | Backend | 0.5h |
| Conflicting settings | Misconfig, time zone errors | Keep DEBUG from Env; Africa/Nairobi TZ; guard ALLOWED_HOSTS (done) | Backend | 0.5h |
| Payments model split | Duplicate logic/bugs | Consolidate on payments.Transaction; migrate data | Backend | 8–12h |
| Readiness probe | Missing readiness | Add /readyz DB check (done) | DevOps | 0.5h |
| Vendor 400s | Broken dashboards | Ensure owner_id resolution; improve 400 messages | API | 2h |
| Checkout regression | UX block | Harden ChatPanel button (done); verify | Frontend | 0.5h |
| CI matrix | Low coverage | Add pytest, websocket, webhook tests; lint | DevOps | 3–5h |
| Static build drift | CSS/JS churn | Pin Node versions; use npm ci; document build | Frontend | 1–2h |
| Channels Redis | Missing prod config | Provide REDIS_URL and worker scaling guide | DevOps | 1h |

5. Security & Compliance

- Secrets must be removed from repository and rotated. Use Render/DO secret managers.
- CSRF_TRUSTED_ORIGINS, SECURE_* headers configured for prod. HSTS set when ENV=prod.
- Rate limiting via DRF throttles (user:120/min). Consider login throttling.
- Bandit/dep scan to run in CI (commands below).

6. Reliability, Observability & Alerts

- Logging: root, django, channels configured to INFO; request ID middleware adds X-Request-ID.
- Health: /healthz (liveness), /readyz (readiness) added.
- Suggest Sentry integration via SENTRY_DSN env hook in settings.

7. Performance & DB Index Review

- Indexes present on transactions, deliveries. Use select_related/prefetch_related in hot paths (users/views.py my_orders optimized).
- Ensure MySQL key lengths for utf8mb4 (191) on indexed varchars; present on users.CustomUser.email=191.

8. Payments & Webhooks (idempotency, retries, signatures)

- Idempotent checkout via idempotency_key (payments.services.init_checkout) and optimistic get_or_create.
- Signature verification:
  - Stripe: stripe.Webhook.construct_event
  - Paystack: HMAC-SHA512 of body with PAYSTACK_SECRET_KEY
  - M-Pesa: payload shape check; consider signing if using Daraja
- Replay-safe webhooks: replay guarded via status and PaymentEvent (orders) or AuditLog entries.
- Duplicate-success auto-refund handled for Stripe/Paystack (payments.services.process_success + issue_refund stub).

9. Realtime (Channels/WebSockets) validation

- ASGI import order correct; URLRouter composes orders + notifications.
- Consumers enforce auth and per-delivery access; throttle and haversine distance filter present.
- Must use Redis in prod (fixed). Add heartbeat/ping in client and auto-reconnect in UI if needed.

10. Frontend Build & Checkout UX

- Tailwind v4 via CLI + Vite. Ensure consistent build: use npm ci and pinned versions.
- Assistant ChatPanel hardened to avoid submit interception; pointer-events on root already safe.

11. Deployment Playbooks (Render staging, DigitalOcean prod)

- Render (staging):
  - Set env: DJANGO_SETTINGS_MODULE, SECRET_KEY, DEBUG=0, ENV=staging, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, REDIS_URL, DATABASE_URL (Postgres), STRIPE_*, PAYSTACK_*, PAYPAL_*, EMAIL_*
  - Gunicorn/Daphne: daphne -b 0.0.0.0 -p $PORT Rahim_Online_ClothesStore.asgi:application
  - Background worker (if using Channels workers for tasks): scale dyno accordingly
  - Run collectstatic on build; enable WhiteNoise
  - Health checks: /healthz, /readyz

- DigitalOcean (prod):
  - Systemd services for daphne and a process manager (supervisor/systemd) for workers
  - Nginx with TLS, proxy to daphne; set proxy headers X-Forwarded-Proto
  - Redis (Managed or Droplet), Postgres (Managed)
  - Env vars in DO App Platform or droplet .env files with proper permissions
  - Backups and log shipping

12. Test Plan & CI matrix

- Install & run:
  - pip install -r requirements.txt
  - npm ci
  - python manage.py check --deploy
  - pytest -q
- Tests added in this patch under tests_added/:
  - tests_added/test_settings_channel_layer.py
  - tests_added/test_vendor_permissions.py
  - tests_added/test_payments_webhook_signature.py
- WebSocket example (manual):
  - Login as driver and customer; open ws://host/ws/delivery/track/<id>/; send {"type":"position_update","lat":-1.3,"lng":36.8}
- Payment webhook simulation (dev):
  - Stripe: curl -H "Stripe-Signature: …" -d '{"type":"payment_intent.succeeded","data":{"object":{"metadata":{"reference":"REF"},"payment_intent":"pi_1"}}}' http://127.0.0.1:8000/webhook/stripe/
  - Paystack: python manage.py reconcile_paystack (for stale tx); or curl with HMAC header

13. Final Go-Live Checklist

- Secrets: rotated and not in repo; env vars configured on hosts
- DEBUG=0, ENV=prod, ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS set
- REDIS_URL set; Channels uses Redis (not InMemory)
- DATABASE_URL points to Postgres; migrations applied cleanly
- Static built (npm ci && npm run build) and collectstatic run
- Health and readiness checks green behind load balancer
- Payment webhooks reachable over HTTPS, secrets configured; idempotency keys in place
- Logs and alerts wired (Sentry optional)

