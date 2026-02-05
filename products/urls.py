from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('add/', views.add_product, name='add'),
    path('edit/<int:pk>/', views.edit_product, name='edit'),
    path('delete/<int:pk>/', views.delete_product, name='delete'),
]
