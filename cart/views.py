import json
import traceback

from django.conf import settings
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from orders.forms import OrderForm
from product_app.models import Product, ProductStock
from users.permissions import NotBuyingOwnListing

from .models import Cart, CartItem


# cart/views.py
def wants_json(request):
    accept = request.headers.get("Accept", "")
    xrw = request.headers.get("X-Requested-With", "")
    return "application/json" in accept or xrw == "XMLHttpRequest"


def _json_ok(message, *, count=None, extra=None, status=201):
    payload = {"success": True, "code": "OK", "message": message}
    if count is not None:
        payload["count"] = count
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _json_err(message, *, code="ERROR", status=400, extra=None):
    payload = {"success": False, "code": code, "message": message}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


@require_POST
def cart_add(request, product_id):
    try:
        # --- auth gate ---
        if not request.user.is_authenticated:
            login_url = f"{settings.LOGIN_URL}?next={request.get_full_path()}"
            if wants_json(request):
                return _json_err(
                    "Please log in to continue.",
                    code="AUTH_REQUIRED",
                    status=401,
                    extra={"login_url": login_url},
                )
            return redirect(login_url)

        product = get_object_or_404(Product, id=product_id)

        # quantity from JSON/form; default = 1
        qty = 1
        if request.body:
            try:
                qty = int(json.loads(request.body).get("quantity", 1))
            except Exception:
                pass
        else:
            try:
                qty = int(request.POST.get("quantity", 1))
            except Exception:
                qty = 1
        if qty < 1:
            return _json_err("Quantity must be at least 1.", code="INVALID_QUANTITY", status=400)

        # not buying own listing
        perm = NotBuyingOwnListing()
        if not perm.has_object_permission(request, None, product):
            return _json_err(
                perm.message or "You cannot purchase your own product.",
                code="OWN_LISTING",
                status=403,
            )

        # optional stock + availability checks
        if hasattr(product, "available") and not product.available:
            return _json_err("Product is not available.", code="UNAVAILABLE", status=409)

        available = (
            ProductStock.objects.filter(product=product).aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        if qty > available:
            return _json_err(f"Only {available} left in stock.", code="OUT_OF_STOCK", status=409)

        # session cart
        cart_id = request.session.get("cart_id")
        if cart_id:
            cart, _ = Cart.objects.get_or_create(id=cart_id)
        else:
            cart = Cart.objects.create()
            request.session["cart_id"] = cart.id

        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        item.quantity = (item.quantity if not created else 0) + qty
        item.save()

        request.session["cart_count"] = int(request.session.get("cart_count", 0)) + qty

        return _json_ok(
            f"Added {qty} × {product.name} to cart.",
            count=request.session["cart_count"],
            extra={"item_id": item.id, "product_id": product.id, "quantity": item.quantity},
            status=201,
        )

    except Exception as e:
        print("Error in cart_add:", e)
        traceback.print_exc()
        return _json_err("Something went wrong. Please try again.", code="SERVER_ERROR", status=500)


def cart_count(request):
    cart_id = request.session.get("cart_id")

    if not cart_id:
        return JsonResponse({"count": 0})

    try:
        cart = Cart.objects.get(id=cart_id)
        total_items = sum(item.quantity for item in cart.items.all())  # Count quantity across items
        return JsonResponse({"count": total_items})
    except Cart.DoesNotExist:
        return JsonResponse({"count": 0})


def cart_detail(request):
    try:
        cart_id = request.session.get("cart_id")
        cart = Cart.objects.get(id=cart_id)

        if not cart.items.exists():
            return redirect("products:list")

        cart_items = cart.items.select_related("product")
        total_price = sum(item.product.price * item.quantity for item in cart_items)

        order_form = OrderForm()

        return render(
            request,
            "cart/cart_detail.html",
            {
                "cart": cart,
                "cart_items": cart_items,
                "total_price": total_price,
                "order_form": order_form,
            },
        )

    except (Cart.DoesNotExist, KeyError):
        request.session.pop("cart_id", None)
        return render(
            request,
            "cart/cart_detail.html",
            {
                "cart": None,
                "cart_items": [],
                "total_price": 0,
                "order_form": OrderForm(),
            },
        )

    except (Cart.DoesNotExist, KeyError):
        if "cart_id" in request.session:
            del request.session["cart_id"]
        return render(
            request, "cart/cart_detail.html", {"cart": None, "cart_items": [], "total_price": 0}
        )


def get_cart_data(request):
    cart_id = request.session.get("cart_id")
    try:
        cart = Cart.objects.get(id=cart_id)
        cart_items = []
        for item in cart.items.select_related("product"):
            cart_items.append(
                {
                    "id": item.id,
                    "product": {
                        "id": item.product.id,
                        "name": item.product.name,
                        "description": item.product.description,
                        "price": str(
                            item.product.price
                        ),  # Convert Decimal to string for JSON serialization
                        "image_url": item.product.image.url if item.product.image else "",
                        "detail_url": item.product.get_absolute_url(),
                    },
                    "quantity": item.quantity,
                }
            )

        return JsonResponse({"cart_items": cart_items, "exists": True})

    except Cart.DoesNotExist:
        return JsonResponse({"cart_items": [], "exists": False})


def cart_remove(request, product_id):
    cart_id = request.session.get("cart_id")

    if not cart_id:
        return redirect("cart:cart_detail")

    try:
        cart = Cart.objects.get(id=cart_id)

        try:
            item = CartItem.objects.get(cart=cart, product__id=product_id)
            item.delete()

            if "cart_count" in request.session:
                request.session["cart_count"] = max(
                    0, request.session["cart_count"] - item.quantity
                )

            # Delete cart if empty and clean session
            if not cart.items.exists():
                cart.delete()
                del request.session["cart_id"]
                if "cart_count" in request.session:
                    del request.session["cart_count"]
        except CartItem.DoesNotExist:
            # The specific item wasn't found - just continue to cart
            pass

    except Cart.DoesNotExist:
        # Clean up session if cart doesn't exist
        if "cart_id" in request.session:
            del request.session["cart_id"]
        if "cart_count" in request.session:
            del request.session["cart_count"]

    return redirect("cart:cart_detail")


@require_POST
def cart_increment(request, product_id):
    """Increase quantity of a specific cart item by 1"""
    cart_id = request.session.get("cart_id")
    if not cart_id:
        return redirect("cart:cart_detail")

    try:
        cart = Cart.objects.get(id=cart_id)
        item = CartItem.objects.get(cart=cart, product__id=product_id)

        # Increase quantity
        item.quantity += 1
        item.save()

        # Update session cart_count
        if "cart_count" in request.session:
            request.session["cart_count"] += 1

        messages.success(request, f"Added one more {item.product.name}")

    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        messages.error(request, "Item not found in cart")

    return redirect("cart:cart_detail")


@require_POST
def cart_decrement(request, product_id):
    """Decrease quantity of a specific cart item by 1"""
    cart_id = request.session.get("cart_id")
    if not cart_id:
        return redirect("cart:cart_detail")

    try:
        cart = Cart.objects.get(id=cart_id)
        item = CartItem.objects.get(cart=cart, product__id=product_id)

        # Decrease quantity or remove if 1
        if item.quantity > 1:
            item.quantity -= 1
            item.save()

            # Update session cart_count
            if "cart_count" in request.session:
                request.session["cart_count"] = max(0, request.session["cart_count"] - 1)

            messages.info(request, f"Removed one {item.product.name}")
        else:
            # Remove item completely if quantity would become 0
            item.delete()

            # Update session cart_count
            if "cart_count" in request.session:
                request.session["cart_count"] = max(0, request.session["cart_count"] - 1)

            messages.info(request, f"Removed {item.product.name} from cart")

            # Delete cart if empty
            if not cart.items.exists():
                cart.delete()
                del request.session["cart_id"]

    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        messages.error(request, "Item not found in cart")

    return redirect("cart:cart_detail")
