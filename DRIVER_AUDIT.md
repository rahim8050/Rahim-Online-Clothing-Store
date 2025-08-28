PAYSTACK_PUBLIC_KEY:  …
PAYSTACK_SECRET_KEY:  …
# Driver Domain Profile — Auto Audit
## Driver Model Sheet
- Model: `orders.models.Delivery`  *(defined at orders/models.py:128)*
- Status choices: `pending, assigned, picked_up, en_route, delivered, cancelled`
### Fields
- `id`: BigAutoField  null=False blank=True index=False related_name=None
- `order`: ForeignKey  null=False blank=False index=True related_name=deliveries
- `driver`: ForeignKey  null=True blank=True index=True related_name=deliveries
- `status`: CharField  null=False blank=False index=True related_name=None
- `assigned_at`: DateTimeField  null=True blank=True index=False related_name=None
- `picked_up_at`: DateTimeField  null=True blank=True index=False related_name=None
- `delivered_at`: DateTimeField  null=True blank=True index=False related_name=None
- `origin_lat`: DecimalField  null=True blank=True index=False related_name=None
- `origin_lng`: DecimalField  null=True blank=True index=False related_name=None
- `dest_lat`: DecimalField  null=False blank=False index=False related_name=None
- `dest_lng`: DecimalField  null=False blank=False index=False related_name=None
- `last_lat`: FloatField  null=True blank=True index=False related_name=None
- `last_lng`: FloatField  null=True blank=True index=False related_name=None
- `last_ping_at`: DateTimeField  null=True blank=True index=False related_name=None
- `channel_key`: CharField  null=False blank=False index=False related_name=None
- `created_at`: DateTimeField  null=False blank=True index=False related_name=None
- `updated_at`: DateTimeField  null=False blank=True index=False related_name=None

### Indexes
- orders_deli_order_i_2374e2_idx: fields=['order', 'status']
- orders_deli_driver__adb7af_idx: fields=['driver', 'status']
- orders_deli_last_pi_225781_idx: fields=['last_ping_at']

### Constraints
- delivery_driver_required_when_moving (CheckConstraint): `(OR: ('status__in', ['pending', 'delivered', 'cancelled']), ('driver__isnull', False))`
- delivery_dest_lat_range (CheckConstraint): `(AND: ('dest_lat__gte', -90), ('dest_lat__lte', 90))`
- delivery_dest_lng_range (CheckConstraint): `(AND: ('dest_lng__gte', -180), ('dest_lng__lte', 180))`
- delivery_origin_lat_range (CheckConstraint): `(OR: ('origin_lat__isnull', True), (AND: ('origin_lat__gte', -90), ('origin_lat__lte', 90)))`
- delivery_origin_lng_range (CheckConstraint): `(OR: ('origin_lng__isnull', True), (AND: ('origin_lng__gte', -180), ('origin_lng__lte', 180)))`

## Read/Write Matrix
| Component | Reads | Writes | File:Line |
|---|---|---|---|
| DriverDeliveriesAPI.get | Delivery by driver | - | apis/views.py:160 |
| DeliveryAssignAPI.post | Delivery | driver,status,assigned_at + WS assign | apis/views.py:170 |
| DeliveryUnassignAPI.post | Delivery | driver=None,status=pending,assigned_at=None + WS assign | apis/views.py:184 |
| DeliveryAcceptAPI.post | Delivery | driver=self,status=assigned,assigned_at + WS assign | apis/views.py:197 |
| DeliveryStatusAPI.post | Delivery | status(+picked_up_at/delivered_at) + WS status | apis/views.py:208 |
| DriverLocationAPI.post | - | last_lat/last_lng/last_ping_at + WS position | apis/views.py:226 |
| DeliveryConsumer.receive_json | Delivery id from URL | position.update/status.update | orders/consumers.py:18 |

## API & WS Surface
### URLs (filtered)
- `orders/save-location/` → `orders.views.save_location`
- `orders/orders/<int:order_id>/track/` → `orders.views.track_order`
- `driver-dashboard/` → `users.views.driver_dashboard`
- `driver-dashboard/` → `users.views.driver_dashboard`
- `apis/driver/deliveries/` → `apis.views.View.as_view.<locals>.view`
- `apis/driver/location/` → `apis.views.View.as_view.<locals>.view`
- `apis/deliveries/<int:pk>/assign/` → `apis.views.View.as_view.<locals>.view`
- `apis/deliveries/<int:pk>/unassign/` → `apis.views.View.as_view.<locals>.view`
- `apis/deliveries/<int:pk>/accept/` → `apis.views.View.as_view.<locals>.view`
- `apis/deliveries/<int:pk>/status/` → `apis.views.View.as_view.<locals>.view`

### WebSocket
- Routing file hits: `orders/routing.py`, samples: `    re_path(r"^ws/deliveries/(?P<delivery_id>\d+)/$", DeliveryConsumer.as_asgi())`
- Consumer methods present:
  - delivery_event: NO
  - position_update: YES
  - status_update: YES
  - receive_json: YES
- WS events sent:
  - group_send_delivery_event: NO
  - group_send_position_update: YES
  - group_send_status_update: YES

### Serializers
- DeliverySerializer: apis/serializers.py:69
- DeliveryAssignSerializer: apis/serializers.py:77
- DeliveryUnassignSerializer: apis/serializers.py:81
- DeliveryStatusSerializer: apis/serializers.py:85

## Frontend Listeners
- `static/js/tracking-route.js` WebSocket constructors found: 1
- `templates/orders/track.html` wsUrl/route_ctx hits: 1

## Admin & Tests
- Delivery registered in admin: **NO**  (orders/admin.py)
- WS tests present: **YES**  (orders/test_delivery_ws.py)
- API tests under `apis/tests/`: apis/tests/test_shopable_products.py

## Invariants / Business Rules (from code)
- Driver required once moving (check constraint on status).
- Latitude/Longitude range checks on origin/dest/last.
- Status timestamps: assigned_at/picked_up_at/delivered_at maintained by APIs/consumer.
- WebSocket group name uses `delivery.<id>`.

## Gaps & Risks (detected heuristically)
- Delivery not registered in admin (reduced ops visibility).
- consumer missing delivery_event() (REST→WS bridge relies on this).
- views may not publish WS events (`delivery.event`).

## Fix/Enhancement TODOs (ranked)
1) Ensure REST→WS bridge: helper `_publish_delivery(...)` and `delivery_event` handler in consumer.
2) Add tests for assign/unassign/accept/status/location APIs.
3) Admin: register Delivery with list_display, filters, search.
4) Enforce allowed status transitions (assigned→picked_up→en_route→delivered/cancelled).
5) Frontend: reconnect & wsUrl fallback; handle `assign/status/position`.

