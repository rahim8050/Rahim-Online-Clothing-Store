from django.contrib.auth.decorators import login_required
from django.views import View
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, get_object_or_404
from product_app.models import Product


from .models import Category,Product
# Create your views here.
def product_list(request,category_slug=None):
    
    category = None
    products = Product.objects.filter(available=True)
    categories = Category.objects.all()
    if category_slug:
        category = get_object_or_404(Category,slug=category_slug)
        products = products.filter(category=category)

    return render(request, 'products/product/list.html',{
        'category': category,
        'products': products,
        'categories': categories,
    })

    

def product_detail(request,id,slug):
    product = get_object_or_404(Product,id=id,slug=slug,available=True)
    return render(request,'products/product/detail.html',{
        'product': product,
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