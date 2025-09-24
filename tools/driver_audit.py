#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

import django
from django.apps import apps
from django.contrib.admin.sites import site as admin_site
from django.urls import URLPattern, URLResolver, get_resolver

# --- Django bootstrap (no DB use) ---
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")
os.environ.setdefault("SECRET_KEY", "dummy")

django.setup()

# --------------- helpers ---------------
def read_text(rel):
    p = BASE_DIR / rel
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""

def grep_lines(rel, pattern):
    out = []
    p = BASE_DIR / rel
    if not p.exists():
        return out
    rx = re.compile(pattern)
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            if rx.search(line):
                out.append((rel, i, line.rstrip()))
    return out

def find_def_line(rel, name):
    hits = grep_lines(rel, rf"^\s*(class|def)\s+{re.escape(name)}\b")
    return hits[0][:2] if hits else (rel, None)

def iter_patterns(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLPattern):
            path = prefix + str(p.pattern)
            cb = p.callback
            view_name = (
                f"{cb.__module__}.{getattr(cb, '__qualname__', getattr(cb, '__name__', repr(cb)))}"
            )
            yield path, view_name
        elif isinstance(p, URLResolver):
            yield from iter_patterns(p.url_patterns, prefix + str(p.pattern))

def model_fields_sheet(model):
    rows = []
    for f in model._meta.get_fields():
        # only concrete-ish fields
        itype = getattr(f, "get_internal_type", lambda: type(f).__name__)()
        entry = {
            "name": f.name,
            "type": itype,
            "null": getattr(f, "null", None),
            "blank": getattr(f, "blank", None),
            "choices": getattr(f, "choices", None),
            "db_index": getattr(f, "db_index", None),
            "related_name": getattr(getattr(f, "remote_field", None), "related_name", None),
        }
        rows.append(entry)
    return rows

def model_constraints(model):
    out = []
    for c in model._meta.constraints:
        kind = type(c).__name__
        expr = getattr(c, "condition", None) or getattr(c, "check", None)
        out.append({"kind": kind, "name": c.name, "expr": str(expr)})
    return out

def model_indexes(model):
    return [
        {"name": getattr(ix, "name", None), "fields": getattr(ix, "fields", None)}
        for ix in model._meta.indexes
    ]

# --------------- inputs / scanning ---------------
Delivery = apps.get_model("orders", "Delivery")
Order = apps.get_model("orders", "Order")

files_to_scan = {
    "models": "orders/models.py",
    "views": "apis/views.py",
    "serializers": "apis/serializers.py",
    "consumers": "orders/consumers.py",
    "routing": "orders/routing.py",
    "urls_root": "Rahim_Online_ClothesStore/urls.py",
    "apis_urls": "apis/urls.py",
    "orders_urls": "orders/urls.py",
    "users_permissions": "users/permissions.py",
    "users_constants": "users/constants.py",
    "users_views": "users/views.py",
    "driver_dash_tpl": "templates/dash/driver.html",
    "track_tpl": "templates/orders/track.html",
    "track_js": "static/js/tracking-route.js",
    "ws_tests": "orders/test_delivery_ws.py",
    "admin": "orders/admin.py",
    "asgi": "Rahim_Online_ClothesStore/asgi.py",
}

texts = {k: read_text(v) for k, v in files_to_scan.items()}

# key symbol lines
defline_delivery = find_def_line(files_to_scan["models"], "Delivery")
defline_consumer = find_def_line(files_to_scan["consumers"], "DeliveryConsumer")

# URL patterns
all_urls = list(iter_patterns(get_resolver().url_patterns))
url_filter = re.compile(r"(driver|deliver|assign|unassign|status|location|track|ws/)", re.I)
filtered_urls = [(u, v) for (u, v) in all_urls if url_filter.search(u)]

# consumers: methods & events
consumer_methods = {
    "delivery_event": grep_lines(files_to_scan["consumers"], r"^\s*async\s+def\s+delivery_event\b"),
    "position_update": grep_lines(
        files_to_scan["consumers"], r"^\s*async\s+def\s+position_update\b"
    ),
    "status_update": grep_lines(files_to_scan["consumers"], r"^\s*async\s+def\s+status_update\b"),
    "receive_json": grep_lines(files_to_scan["consumers"], r"^\s*async\s+def\s+receive_json\b"),
}
event_sends = {
    "group_send_delivery_event": grep_lines(
        files_to_scan["views"], r"group_send\(.+?delivery\.event"
    ),
    "group_send_position_update": grep_lines(
        files_to_scan["consumers"], r'"type":\s*"position\.update"'
    ),
    "group_send_status_update": grep_lines(
        files_to_scan["consumers"], r'"type":\s*"status\.update"'
    ),
}

# views: API classes (assign/unassign/accept/status/location)
view_classes = {}
for name in [
    "DriverDeliveriesAPI",
    "DeliveryAssignAPI",
    "DeliveryUnassignAPI",
    "DeliveryAcceptAPI",
    "DeliveryStatusAPI",
    "DriverLocationAPI",
]:
    view_classes[name] = find_def_line(files_to_scan["views"], name)

# serializers present?
serializer_hits = {
    "DeliverySerializer": grep_lines(files_to_scan["serializers"], r"class\s+DeliverySerializer\b"),
    "DeliveryAssignSerializer": grep_lines(
        files_to_scan["serializers"], r"class\s+DeliveryAssignSerializer\b"
    ),
    "DeliveryUnassignSerializer": grep_lines(
        files_to_scan["serializers"], r"class\s+DeliveryUnassignSerializer\b"
    ),
    "DeliveryStatusSerializer": grep_lines(
        files_to_scan["serializers"], r"class\s+DeliveryStatusSerializer\b"
    ),
}

# WS routing path
ws_paths = []
ws_paths += [m[2] for m in grep_lines(files_to_scan["routing"], r"ws/[^\"')]+")]

# frontend listeners
ws_new_socket = grep_lines(files_to_scan["track_js"], r"new\s+WebSocket\(")
ws_url_injection = grep_lines(files_to_scan["track_tpl"], r"wsUrl|route_ctx")

# admin registration
admin_registered = Delivery in admin_site._registry

# tests
ws_tests_present = bool(texts["ws_tests"])
api_tests = []
apis_tests_dir = BASE_DIR / "apis/tests"
if apis_tests_dir.exists():
    api_tests = [str(p.relative_to(BASE_DIR)) for p in apis_tests_dir.glob("test_*.py")]

# invariants & statuses
status_choices = [c[0] for c in Delivery.Status.choices]
constraints = model_constraints(Delivery)
indexes = model_indexes(Delivery)
fields = model_fields_sheet(Delivery)

# --------------- render markdown ---------------
md = []
md.append("# Driver Domain Profile â€” Auto Audit\n")
md.append("## Driver Model Sheet\n")
mdl_file, mdl_line = defline_delivery
md.append(f"- Model: `orders.models.Delivery`  *(defined at {mdl_file}:{mdl_line})*\n")
md.append(f"- Status choices: `{', '.join(status_choices)}`\n")
md.append("### Fields\n")
for f in fields:
    md.append(
        f"- `{f['name']}`: {f['type']}  null={f['null']} blank={f['blank']} index={f['db_index']} related_name={f['related_name']}\n"
    )
md.append("\n### Indexes\n")
for ix in indexes:
    md.append(f"- {ix['name']}: fields={ix['fields']}\n")
md.append("\n### Constraints\n")
for c in constraints:
    md.append(f"- {c['name']} ({c['kind']}): `{c['expr']}`\n")

md.append("\n## Read/Write Matrix\n")
md.append("| Component | Reads | Writes | File:Line |\n|---|---|---|---|\n")
matrix_rows = [
    (
        "DriverDeliveriesAPI.get",
        "Delivery by driver",
        "-",
        f"{view_classes['DriverDeliveriesAPI'][0]}:{view_classes['DriverDeliveriesAPI'][1]}",
    ),
    (
        "DeliveryAssignAPI.post",
        "Delivery",
        "driver,status,assigned_at + WS assign",
        f"{view_classes['DeliveryAssignAPI'][0]}:{view_classes['DeliveryAssignAPI'][1]}",
    ),
    (
        "DeliveryUnassignAPI.post",
        "Delivery",
        "driver=None,status=pending,assigned_at=None + WS assign",
        f"{view_classes['DeliveryUnassignAPI'][0]}:{view_classes['DeliveryUnassignAPI'][1]}",
    ),
    (
        "DeliveryAcceptAPI.post",
        "Delivery",
        "driver=self,status=assigned,assigned_at + WS assign",
        f"{view_classes['DeliveryAcceptAPI'][0]}:{view_classes['DeliveryAcceptAPI'][1]}",
    ),
    (
        "DeliveryStatusAPI.post",
        "Delivery",
        "status(+picked_up_at/delivered_at) + WS status",
        f"{view_classes['DeliveryStatusAPI'][0]}:{view_classes['DeliveryStatusAPI'][1]}",
    ),
    (
        "DriverLocationAPI.post",
        "-",
        "last_lat/last_lng/last_ping_at + WS position",
        f"{view_classes['DriverLocationAPI'][0]}:{view_classes['DriverLocationAPI'][1]}",
    ),
    (
        "DeliveryConsumer.receive_json",
        "Delivery id from URL",
        "position.update/status.update",
        f"{defline_consumer[0]}:{defline_consumer[1]}",
    ),
]
for r in matrix_rows:
    md.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n")

md.append("\n## API & WS Surface\n")
md.append("### URLs (filtered)\n")
for u, v in filtered_urls:
    md.append(f"- `{u}` â†’ `{v}`\n")
md.append("\n### WebSocket\n")
md.append(
    f"- Routing file hits: `{files_to_scan['routing']}`, samples: `{'; '.join(ws_paths) or 'n/a'}`\n"
)
md.append("- Consumer methods present:\n")
for k, v in consumer_methods.items():
    md.append(f"  - {k}: {'YES' if v else 'NO'}\n")
md.append("- WS events sent:\n")
for k, v in event_sends.items():
    md.append(f"  - {k}: {'YES' if v else 'NO'}\n")

md.append("\n### Serializers\n")
for k, v in serializer_hits.items():
    if v:
        f, ln, _ = v[0]
        md.append(f"- {k}: {f}:{ln}\n")

md.append("\n## Frontend Listeners\n")
md.append(f"- `{files_to_scan['track_js']}` WebSocket constructors found: {len(ws_new_socket)}\n")
md.append(f"- `{files_to_scan['track_tpl']}` wsUrl/route_ctx hits: {len(ws_url_injection)}\n")

md.append("\n## Admin & Tests\n")
md.append(
    f"- Delivery registered in admin: **{'YES' if admin_registered else 'NO'}**  ({files_to_scan['admin']})\n"
)
md.append(
    f"- WS tests present: **{'YES' if bool(texts['ws_tests']) else 'NO'}**  ({files_to_scan['ws_tests']})\n"
)
md.append(f"- API tests under `apis/tests/`: {', '.join(api_tests) or 'none'}\n")

md.append("\n## Invariants / Business Rules (from code)\n")
md.append("- Driver required once moving (check constraint on status).\n")
md.append("- Latitude/Longitude range checks on origin/dest/last.\n")
md.append(
    "- Status timestamps: assigned_at/picked_up_at/delivered_at maintained by APIs/consumer.\n"
)
md.append("- WebSocket group name uses `delivery.<id>`.\n")

md.append("\n## Gaps & Risks (detected heuristically)\n")
if not admin_registered:
    md.append("- Delivery not registered in admin (reduced ops visibility).\n")
if not consumer_methods["delivery_event"]:
    md.append("- consumer missing delivery_event() (RESTâ†’WS bridge relies on this).\n")
if not event_sends["group_send_delivery_event"]:
    md.append("- views may not publish WS events (`delivery.event`).\n")
if not serializer_hits["DeliverySerializer"]:
    md.append("- DeliverySerializer not found in apis/serializers.py.\n")

md.append("\n## Fix/Enhancement TODOs (ranked)\n")
md.append(
    "1) Ensure RESTâ†’WS bridge: helper `_publish_delivery(...)` and `delivery_event` handler in consumer.\n"
)
md.append("2) Add tests for assign/unassign/accept/status/location APIs.\n")
md.append("3) Admin: register Delivery with list_display, filters, search.\n")
md.append(
    "4) Enforce allowed status transitions (assignedâ†’picked_upâ†’en_routeâ†’delivered/cancelled).\n"
)
md.append("5) Frontend: reconnect & wsUrl fallback; handle `assign/status/position`.\n")

print("".join(md))
