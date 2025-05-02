from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
# Аутентификация и пользователи
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth import get_user_model
# Модели
from .models import (Book,Product,Cart, CartItem,Order,OrderItem)
# Формы
from .forms import (RegisterForm,LoginForm,BookForm)
# Аннотации и агрегации
from django.db.models import Sum
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from .models import Book
User = get_user_model()


def book_list(request):
    books = Book.objects.all()

    # Фильтрация по цене
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    if min_price:
        books = books.filter(price__gte=float(min_price))
    if max_price:
        books = books.filter(price__lte=float(max_price))

    # Сортировка
    sort_by = request.GET.get('sort_by')
    if sort_by == 'title_asc':
        books = books.order_by('title')
    elif sort_by == 'title_desc':
        books = books.order_by('-title')
    elif sort_by == 'price_asc':
        books = books.order_by('price')
    elif sort_by == 'price_desc':
        books = books.order_by('-price')

    paginator = Paginator(books, 2)
    page_number = request.GET.get('page')
    try:
        books_page = paginator.page(page_number)
    except PageNotAnInteger:
        # Если page не число, показываем первую страницу
        books_page = paginator.page(1)
    except EmptyPage:
        # Если page вне диапазона, показываем последнюю страницу
        books_page = paginator.page(paginator.num_pages)

        # Получаем параметры для сохранения в пагинации
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']

    context = {
        'books': books_page,
        'get_params': get_params.urlencode(),
    }
    return render(request, 'echo/book_list.html', {'books': books})
@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    return render(request, 'echo/book_detail.html', {'book': book})

@login_required
def book_new(request):
    if request.method == "POST":
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save()
            return redirect('book_detail', pk=book.pk)
    else:
        form = BookForm()
    return render(request, 'echo/book_edit.html', {'form': form})

@login_required
def book_edit(request, pk):
    if not request.user.is_superuser:
        print(f"Юзер {request.user} пытался редактировать книгу, но он не админ!")  # Смотри в консоль!
        return HttpResponseForbidden("Ты не админ")
    book = get_object_or_404(Book, pk=pk)
    if request.method == "POST":
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            book = form.save()
            return redirect('book_detail', pk=book.pk)
    else:
        form = BookForm(instance=book)
    return render(request, 'echo/book_edit.html', {'form': form})

@login_required
def book_delete(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden("У вас нет прав для удаления книг!")
    book = get_object_or_404(Book, pk=pk)
    book.delete()
    return redirect('book_list')

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email'].lower()
            user.save()
            login(request, user)
            return redirect('book_list')
        else:
            print(form.errors)
    else:
        form = RegisterForm()
    return render(request, 'echo/register.html', {'form': form})

def check_username(request):
    username = request.GET.get('username', '')
    exists = User.objects.filter(username__iexact=username).exists()
    return JsonResponse({'exists': exists})

def check_email(request):
    email = request.GET.get('email', '')
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'exists': exists})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('book_list')
    else:
        form = LoginForm()
    return render(request, 'echo/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('book_list')

def index(request):
    products = Product.objects.all()
    return render(request, 'echo/index.html', {'products': products})

@login_required
def add_to_cart(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        user=request.user,
        book=book,
        defaults={'quantity': 1}
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect('book_detail', pk=book_id)

@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart).select_related('book')
    total = sum(item.get_total_price() for item in cart_items)

    return render(request, 'echo/cart.html', {
        'cart_items': cart_items,
        'total': total
    })

@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        return redirect('view_cart')

    total = sum(item.get_total_price() for item in cart_items)
    order = Order.objects.create(user=request.user, total=total)
    for item in cart_items:
        OrderItem.objects.create(order=order, book=item.book, quantity=item.quantity)
    cart_items.delete()
    return redirect('view_orders')

@login_required
def view_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'echo/orders.html', {'orders': orders})

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    return redirect('view_cart')

@login_required
def update_cart_item(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'increase':
            cart_item.quantity += 1
        elif action == 'decrease' and cart_item.quantity > 1:
            cart_item.quantity -= 1

        cart_item.save()

    return redirect('view_cart')


@login_required
def create_order(request):
    cart = get_object_or_404(Cart, user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)

    if not cart_items.exists():
        messages.warning(request, "Ваша корзина пуста")
        return redirect('view_cart')

    order = Order.objects.create(
        user=request.user,
        total=sum(item.get_total_price() for item in cart_items)
    )
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            book=item.book,
            quantity=item.quantity,
            price=item.book.price
        )
    cart_items.delete()

    messages.success(request, "Заказ успешно оформлен!")
    return redirect('order_detail', order_id=order.id)
from django.contrib import messages

def increase_quantity(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.quantity += 1
    cart_item.save()
    messages.success(request, f"Количество {cart_item.book.title} увеличено")
    return redirect('view_cart')

def decrease_quantity(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
        messages.success(request, f"Количество {cart_item.book.title} уменьшено")
    else:
        cart_item.delete()
        messages.success(request, f"{cart_item.book.title} удален из корзины")
    return redirect('view_cart')

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.delete()
    messages.success(request, f"{cart_item.book.title} удален из корзины")
    return redirect('view_cart')

@login_required
def account(request):
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.email = request.POST.get('email')
        request.user.username = request.POST.get('login')
        request.user.save()
        return redirect('account')
    return render(request, 'echo/account.html', {'user': request.user})



