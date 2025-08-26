from decimal import Decimal
from uuid import uuid4
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import Product, ListingCheckout


def edit_product(product: Product, owner, data: dict) -> Product:
    if product.owner_id != getattr(owner, "id", None):
        raise PermissionDenied("not owner")
    if not product.is_editable():
        raise ValueError("product not editable")
    editable = {"description", "price"}
    if product.status in [Product.Status.DRAFT, Product.Status.AWAITING_PUBLICATION]:
        editable.update({"name", "slug"})
    for field in editable:
        if field in data:
            if field == "price":
                value = Decimal(str(data[field]))
                if value < 0:
                    raise ValueError("price must be non-negative")
                setattr(product, field, value)
            else:
                setattr(product, field, data[field])
    disallowed = set(data.keys()) - editable
    if disallowed:
        raise ValueError("invalid fields: " + ",".join(sorted(disallowed)))
    product.version += 1
    product.save()
    product.listing_checkouts.filter(status=ListingCheckout.Status.OPEN).update(
        status=ListingCheckout.Status.SUPERSEDED
    )
    return product


def start_listing_checkout(product: Product, user, amount, currency):
    if product.owner_id != getattr(user, "id", None):
        raise PermissionDenied("not owner")
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("amount must be positive")
    product.listing_checkouts.filter(status=ListingCheckout.Status.OPEN).update(
        status=ListingCheckout.Status.SUPERSEDED
    )
    if product.status in [Product.Status.DRAFT, Product.Status.PUBLISHED]:
        product.status = Product.Status.AWAITING_PUBLICATION
        product.save(update_fields=["status"])
    checkout = ListingCheckout.objects.create(
        product=product,
        product_version=product.version,
        amount=amount,
        currency=currency,
        status=ListingCheckout.Status.OPEN,
        gateway="",
        provider_ref=uuid4().hex,
        created_by=user,
    )
    return checkout


@transaction.atomic
def handle_listing_webhook(provider_ref: str, success: bool):
    checkout = (
        ListingCheckout.objects.select_for_update().select_related("product").get(
            provider_ref=provider_ref
        )
    )
    product = checkout.product
    if success:
        if product.version == checkout.product_version:
            checkout.status = ListingCheckout.Status.COMPLETED
            checkout.save(update_fields=["status"])
            product.status = Product.Status.PUBLISHED
            product.published_version = product.version
            product.save(update_fields=["status", "published_version"])
        else:
            checkout.status = ListingCheckout.Status.SUPERSEDED
            checkout.save(update_fields=["status"])
    else:
        checkout.status = ListingCheckout.Status.CANCELED
        checkout.save(update_fields=["status"])
    return checkout
