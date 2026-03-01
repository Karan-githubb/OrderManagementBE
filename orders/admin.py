from django.contrib import admin
from .models import Order, OrderItem, OrderItemAllocation, Dispatch


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'pharmacy', 'status', 'total_amount', 'is_void', 'created_at')


@admin.register(Dispatch)
class DispatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'dispatched_at')
    list_filter = ('dispatched_at',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'quantity', 'unit_price', 'is_void')


@admin.register(OrderItemAllocation)
class OrderItemAllocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_item', 'stock_batch', 'quantity', 'dispatch', 'created_at')
    list_filter = ('dispatch',)
