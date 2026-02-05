from django.shortcuts import render, redirect, get_object_or_404
from products.models import Product


def product_list(request):
    products = Product.objects.all()
    return render(request, 'admin_panel/products.html', {'products': products})


def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        description = request.POST.get('description')
        image = request.FILES.get('image')

        Product.objects.create(
            name=name,
            category=category,
            price=price,
            stock=stock,
            description=description,
            image=image
        )
        return redirect('products:list')

    return render(request, 'admin_panel/products.html')

def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.category = request.POST.get('category')
        product.price = request.POST.get('price')
        product.stock = request.POST.get('stock')
        product.description = request.POST.get('description')
        if 'image' in request.FILES:
            product.image = request.FILES.get('image')

        product.save()
        return redirect('products:list')
    return render(request, 'admin_panel/edit_product.html', {'product': product})


def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return redirect('products:list')