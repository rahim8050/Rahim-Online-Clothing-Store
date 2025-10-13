from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product
from .queries import shopable_products_q

import json
from django.utils.safestring import mark_safe

app_name = "product_app"


def product_list(request, category_slug=None):
    categories = Category.objects.all()
    category = None

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=category)
        if request.user.is_authenticated:
            products = products.filter(shopable_products_q(request.user))
    else:
        products = Product.objects.all()
        if request.user.is_authenticated:
            products = products.filter(shopable_products_q(request.user))

    # Serialize products
    product_list = []
    for product in products:
        product_list.append(
            {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": float(product.price),
                "image_url": product.image.url if product.image else "",
                "category_slug": product.category.slug if product.category else "",
                "detail_url": product.get_absolute_url(),
            }
        )

    # Serialize categories
    category_list = [{"id": c.id, "name": c.name, "slug": c.slug} for c in categories]

    pagination_data = {"current_page": 1, "total_pages": 1}

    initial_data = {
        "products": product_list,
        "categories": category_list,
        "pagination": pagination_data,
    }

    # convert to safe JSON
    initial_data_json = mark_safe(json.dumps(initial_data))

    return render(
        request,
        "products/product/list.html",
        {
            "initial_data_json": initial_data_json,
            "category": category,
        },
    )


from django.shortcuts import redirect
from django.db.models import Sum
import json
from django.shortcuts import get_object_or_404, render
from .models import Product, ProductStock


def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id)
    if product.slug != slug:
        return redirect(product.get_absolute_url())

    product_data = {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "price": float(product.price),
        "description": product.description,
    }

    context = {
        "product": product,
        "product_json": json.dumps(product_data),
        "product_data": {
            "total_stock": ProductStock.objects.filter(product=product).aggregate(
                total=Sum("quantity")
            )["total"]
            or 0
        },
    }

    return render(request, "products/product/detail.html", context)


def SearchProduct(request, category_slug=None):
    category = None
    products = Product.objects.all()

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    if "search" in request.GET:
        search_term = request.GET["search"]
        products = products.filter(
            Q(name__icontains=search_term) | Q(description__icontains=search_term)
        )

    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Serialize current page products
    product_list = []
    for product in page_obj.object_list:
        product_list.append(
            {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": str(product.price),
                "image_url": product.image.url if product.image else "",
                "category_slug": product.category.slug if product.category else "",
                "detail_url": product.get_absolute_url(),
            }
        )

    # Serialize categories
    categories = Category.objects.all()
    category_list = []
    for cat in categories:
        category_list.append({"id": cat.id, "name": cat.name, "slug": cat.slug})

    pagination_data = {
        "current_page": page_obj.number,
        "total_pages": paginator.num_pages,
    }

    initial_data = {
        "products": product_list,
        "categories": category_list,
        "pagination": pagination_data,
    }

    return render(
        request,
        "products/product/list.html",
        {
            "category": category,
            "initial_data": initial_data,
        },
    )


# def SearchProduct(request):
#     data = Product.objects.all().order_by('id').values()
#     search_term = request.GET.get('Search', '')
#
#     # Filter products
#     data = Product.objects.filter(
#         Q(name__icontains=search_term) |
#         Q(description__icontains=search_term)
#     ).order_by('id')
#
#     # Pagination
#     paginator = Paginator(data, 15)  # Fixed per_page syntax
#     page = request.GET.get('page', 1)
#
#     try:
#         paginated_data = paginator.page(page)  # Correct method
#     except (EmptyPage, PageNotAnInteger):
#         paginated_data = paginator.page(1)
#
#     return render(request, 'products/product/list.html', {"data": paginated_data})
@login_required
def profile(request):
    return render(request, "users/accounts/profile.html")
