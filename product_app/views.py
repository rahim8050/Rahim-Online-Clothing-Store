from django.contrib.auth.decorators import login_required
from django.views import View
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, get_object_or_404
from product_app.models import Product
from product_app.queries import shopable_products_q
from django.utils.safestring import mark_safe
import json
app_name = 'product_app'
from .models import Category,Product



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
        product_list.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': str(product.price),
            'image_url': product.image.url if product.image else '',
            'category_slug': product.category.slug if product.category else '',
            'detail_url': product.get_absolute_url()
        })

    # Serialize categories
    category_list = []
    for cat in categories:
        category_list.append({
            'id': cat.id,
            'name': cat.name,
            'slug': cat.slug
        })

    pagination_data = {
        'current_page': 1,
        'total_pages': 1
    }

    return render(request, 'products/product/list.html', {
        'categories': json.dumps(category_list),
        'products': json.dumps(product_list),
        'category': category,
        'pagination_data': json.dumps(pagination_data),
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
        'product_json': mark_safe(json.dumps(product_data))  
    })
   
    
    




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