# orders/management/commands/export_eta_training.py
from django.core.management.base import BaseCommand
from django.utils.timezone import make_naive
from orders.models import Delivery
import csv, math

def _f(x):
    return None if x is None or x == "" else float(x)

def haversine_km(a_lat,a_lng,b_lat,b_lng):
    dlat = math.radians(b_lat - a_lat); dlng = math.radians(b_lng - a_lng)
    aa = math.sin(dlat/2)**2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlng/2)**2
    return 2 * 6371.0 * math.asin(math.sqrt(aa))

class Command(BaseCommand):
    help = "Export completed deliveries for ETA model training"

    def add_arguments(self, p):
        p.add_argument("--out", default="eta_training.csv")

    def handle(self, *args, **o):
        qs = (Delivery.objects
              .exclude(picked_up_at=None)
              .exclude(delivered_at=None))

        skips = {"no_ts":0,"no_origin":0,"no_dest":0,"outlier":0}
        rows = 0

        with open(o["out"], "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "delivery_id","driver_id",
                "origin_lat","origin_lng","dest_lat","dest_lng",
                "assigned_hour","assigned_dow",
                "picked_hour","picked_dow",
                "dist_haversine_km",
                "duration_min"  # TARGET
            ])

            for d in qs:
                # timestamps
                if not (d.picked_up_at and d.delivered_at):
                    skips["no_ts"] += 1; continue
                assigned = make_naive(getattr(d, "assigned_at", None)) if getattr(d, "assigned_at", None) else None
                picked   = make_naive(d.picked_up_at)
                delivered= make_naive(d.delivered_at)
                duration_min = (delivered - picked).total_seconds()/60.0
                if duration_min <= 1 or duration_min > 240:
                    skips["outlier"] += 1; continue

                # coords from Delivery itself
                o_lat, o_lng = _f(d.origin_lat), _f(d.origin_lng)
                if o_lat is None or o_lng is None:
                    skips["no_origin"] += 1; continue

                t_lat, t_lng = _f(d.dest_lat), _f(d.dest_lng)
                if t_lat is None or t_lng is None:
                    skips["no_dest"] += 1; continue

                dist_km = haversine_km(o_lat, o_lng, t_lat, t_lng)

                w.writerow([
                    d.id, getattr(d, "driver_id", "") or "",
                    round(o_lat,6), round(o_lng,6), round(t_lat,6), round(t_lng,6),
                    assigned.hour if assigned else "",
                    assigned.weekday() if assigned else "",
                    picked.hour, picked.weekday(),
                    round(dist_km,4),
                    round(duration_min,2),
                ])
                rows += 1

        self.stdout.write(self.style.WARNING(f"Skipped: {skips}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {rows} rows to {o['out']}"))
