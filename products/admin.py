from django.contrib import admin
from .models import Category, Product, Purchase, PurchaseItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'stock_quantity', 'selling_price', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['supplier_name', 'purchase_date', 'total_amount', 'is_paid', 'created_at']
    list_filter = ['is_paid', 'purchase_date']
    search_fields = ['supplier_name', 'notes']
    inlines = [PurchaseItemInline]
