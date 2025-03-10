from django.shortcuts import render, get_object_or_404
from django.utils.text import normalize_newlines

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
    return render(request,'product_app/product/detail.html',{
        'product': product,
    })

