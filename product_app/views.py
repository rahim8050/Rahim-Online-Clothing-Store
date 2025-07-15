from django.contrib.auth.decorators import login_required
from django.views import View
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, get_object_or_404
from product_app.models import Product
from django.utils.safestring import mark_safe
import json

from .models import Category,Product
# Create your views here.
# def product_list(request,category_slug=None):
    
#     category = None
#     products = Product.objects.filter(available=True)
#     categories = Category.objects.all()
#     if category_slug:
#         category = get_object_or_404(Category,slug=category_slug)
#         products = products.filter(category=category)

#     return render(request, 'products/product/list.html',{
#         'category': category,
#         'products': products,
#         'categories': categories,
#     })
def product_list(request, category_slug=None):
    categories = Category.objects.all()
    category = None

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=category)
    else:
        products = Product.objects.all()

    return render(request, 'products/product/list.html', {
        'categories': categories,
        'products': products,
        'category': category,
    })


    

def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)

    product_data = {
        'name': product.name,
        'price': float(product.price),
        'description': product.description
    }

    return render(request, 'products/product/detail.html', {
        'product': product,
        'product_json': mark_safe(json.dumps(product_data))  # ensures Vue receives valid JSON
    })
    product = get_object_or_404(Product, id=id, slug=slug, available=True)

    # Create JSON-safe product data
    product_data = json.dumps({
        'name': product.name,
        'price': str(product.price),  # Ensure price is string
        'description': product.description,
    })

    return render(request, 'products/product/detail.html', {
        'product': product,
        'product_json': mark_safe(product_data),
    })
# def product_detail(request,id,slug):
#     product = get_object_or_404(Product,id=id,slug=slug,available=True)
#     return render(request,'products/product/detail.html',{
#         'product': product,
#     })



def SearchProduct(request, category_slug=None):
    category = None
    products = Product.objects.all()

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    if 'search' in request.GET:
        search_term = request.GET['search']
        products = products.filter(
            Q(name__icontains=search_term) |
            Q(description__icontains=search_term)
        )

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    return render(request, 'products/product/list.html', {
        'category': category,
        'products': products,
        'categories': Category.objects.all()
    })

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
    return render(request, 'users/accounts/profile.html')