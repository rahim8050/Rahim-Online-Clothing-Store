# Pull Request Plan

This document enumerates auto-generated PRs derived from `audit_findings.json`.

## PRs Summary Table

| ID | Branch | Title | Files | Tests |
|---|---|---|---|---|
| CFG-CH-001 | fix/realtime/P0-CFG-CH-001-channels-redis-in-prod | [P0] realtime: CHANNEL_LAYERS uses Redis in prod (#CFG-CH-001) | settings.py | tests_added/test_settings_channel_layer.py |
| SEC-SE-002 | fix/security/P0-SEC-SE-002-secrets-hygiene | [P0] security: secrets hygiene + .env.example (#SEC-SE-002) | settings.py (no secret prints), .env.example | — |
| CFG-ST-003 | fix/backend/P1-CFG-ST-003-settings-conflicts | [P1] backend: resolve conflicting settings (#CFG-ST-003) | settings.py | — |
| OBS-HC-004 | fix/devops/P1-OBS-HC-004-readyz-endpoint | [P1] devops: add /readyz DB readiness (#OBS-HC-004) | core/views.py, Rahim_Online_ClothesStore/urls.py | — |
| UX-CK-005 | fix/frontend/P1-UX-CK-005-chatpanel-submit-guard | [P1] frontend: prevent chat panel submit hijack (#UX-CK-005) | src/components/ChatPanel.vue | — |
| PMT-DUP-006 | fix/payments/P1-PMT-DUP-006-legacy-webhooks-flag | [P1] payments: guard legacy order webhooks via flag (#PMT-DUP-006) | settings.py, orders/views.py | tests_added/test_legacy_payments_flag.py |

---

## CFG-CH-001 – CHANNEL_LAYERS uses Redis in prod

- Branch: fix/realtime/P0-CFG-CH-001-channels-redis-in-prod
- Diff: patches/0001-fix-channels-layer.diff
- Tests: tests_added/test_settings_channel_layer.py
- Verify:
  - $env:REDIS_URL='redis://127.0.0.1:6379/0'; python - << 'PY'\nimport Rahim_Online_ClothesStore.settings as s; print(s.CHANNEL_LAYERS)\nPY
  - pytest -q tests_added/test_settings_channel_layer.py
- PR Title: [P0] realtime: CHANNEL_LAYERS uses Redis in prod (#CFG-CH-001)
- PR Body:
  - Problem Statement: CHANNEL_LAYERS overridden to InMemory in prod broke WS scaling.
  - Root Cause: second assignment of CHANNEL_LAYERS.
  - Changes: conditional backend based on REDIS_URL; removed override.
  - Security/Privacy: none.
  - Migrations/Backfills: none.
  - How to Test: set REDIS_URL and run pytest and check.
  - Rollout Plan & Rollback: deploy; if issues, unset REDIS_URL to use InMemory on dev.

## SEC-SE-002 – secrets hygiene

- Branch: fix/security/P0-SEC-SE-002-secrets-hygiene
- Diff: patches/0005-secrets-cleanup.diff
- Tests: n/a
- Verify: grep -n 'PAYSTACK_.*:' settings shows no prints; ensure .env.example present
- PR Title: [P0] security: secrets hygiene + .env.example (#SEC-SE-002)
- PR Body:
  - Problem Statement: .env contained real secrets and settings printed key prefixes in DEBUG.
  - Root Cause: committed .env and debug prints.
  - Changes: removed prints; added .env.example; docs to rotate secrets.
  - Security/Privacy: high; rotate keys.
  - How to Test: N/A; code review.
  - Rollout Plan & Rollback: rotate and deploy; rollback not applicable.

## CFG-ST-003 – resolve settings conflicts

- Branch: fix/backend/P1-CFG-ST-003-settings-conflicts
- Diff: patches/0002-sanitize-settings-duplicates.diff
- Tests: n/a
- Verify: python - << 'PY'\nimport os;os.environ['ENV']='prod';import Rahim_Online_ClothesStore.settings as s;print(s.DEBUG,s.TIME_ZONE,s.ALLOWED_HOSTS)\nPY
- PR Title: [P1] backend: resolve conflicting settings (#CFG-ST-003)
- PR Body: DEBUG not overridden; TZ=Africa/Nairobi kept; ALLOWED_HOSTS default guarded.

## OBS-HC-004 – add /readyz

- Branch: fix/devops/P1-OBS-HC-004-readyz-endpoint
- Diff: patches/0004-readyz.diff
- Tests: n/a
- Verify: uvicorn …; curl -i /readyz -> 200
- PR Title: [P1] devops: add /readyz DB readiness (#OBS-HC-004)
- PR Body: Adds SELECT 1 readiness; no privacy impact.

## UX-CK-005 – chat panel submit guard

- Branch: fix/frontend/P1-UX-CK-005-chatpanel-submit-guard
- Diff: patches/0003-chatpanel-send-button.diff
- Tests: n/a
- Verify: On checkout page, assistant input no longer submits page form when pressing Enter/click Send.
- PR Title: [P1] frontend: prevent chat panel submit hijack (#UX-CK-005)
- PR Body: set type=button and stop propagation.

## PMT-DUP-006 – legacy webhooks flag

- Branch: fix/payments/P1-PMT-DUP-006-legacy-webhooks-flag
- Diff: patches/0006-legacy-order-payments-flag.diff
- Tests: tests_added/test_legacy_payments_flag.py
- Verify: pytest -q tests_added/test_legacy_payments_flag.py
- PR Title: [P1] payments: guard legacy order webhooks via flag (#PMT-DUP-006)
- PR Body:
  - Problem: duplicate webhook stacks (orders vs payments) cause drift.
  - Root Cause: migration to payments app not completed.
  - Changes: LEGACY_ORDER_PAYMENTS flag; legacy endpoints return 410 when disabled; payments/* remain active.
  - Rollout Plan: stage with LEGACY_ORDER_PAYMENTS=0; verify payments webhooks; then flip in prod.
  - Rollback: set LEGACY_ORDER_PAYMENTS=1.

