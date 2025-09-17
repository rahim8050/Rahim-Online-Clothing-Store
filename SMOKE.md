Quick smoke tests for Vendor RBAC changes

Prereqs
- You have a running dev server and three users: owner, staff1, staff2.
- Obtain session cookies or JWTs for each user below. Replace placeholders.

1) Staff cannot remove staff (expect 403)

curl -i -X POST \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=<STAFF1_SESSION>" \
  -d '{"staff_id": <STAFF2_ID>, "owner_id": <OWNER_ID>}' \
  http://localhost:8000/apis/vendor/staff/<STAFF2_ID>/remove/

2) Owner can remove staff (expect 200)

curl -i -X POST \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=<OWNER_SESSION>" \
  -d '{"staff_id": <STAFF2_ID>, "owner_id": <OWNER_ID>}' \
  http://localhost:8000/apis/vendor/staff/<STAFF2_ID>/remove/

3) Staff can create a product (expect 201)

curl -i -X POST \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=<STAFF1_SESSION>" \
  -d '{
        "name": "Staff Shirt",
        "slug": "staff-shirt-1",
        "price": "10.00",
        "available": true,
        "category": <CATEGORY_ID>,
        "owner_id": <OWNER_ID>
      }' \
  http://localhost:8000/apis/vendor/products/create/

4) CSV export (owner) and import (staff with catalog scope)

curl -i -X GET \
  -H "Cookie: sessionid=<OWNER_SESSION>" \
  "http://localhost:8000/apis/vendor/products/export-csv/?owner_id=<OWNER_ID>"

curl -i -X POST \
  -H "Cookie: sessionid=<STAFF_WITH_CATALOG_SESSION>" \
  -F "owner_id=<OWNER_ID>" \
  -F "file=@/path/to/products.csv" \
  http://localhost:8000/apis/vendor/products/import-csv/

5) Deprecated vendor applications URL returns 307

curl -i -H "Cookie: sessionid=<ANY_AUTH_SESSION>" \
  http://localhost:8000/users/vendor-applications/

Notes
- If you use JWTs, replace Cookie with Authorization: Bearer <token>.
- Ensure Category exists and the slug is unique per POST.
