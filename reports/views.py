from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from orders.models import Order
from products.models import Product
from django.db.models import Sum, Count

class AdminDashboardStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        total_orders = Order.objects.count()
        total_sales = Order.objects.filter(status='delivered').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        pending_orders = Order.objects.filter(status='pending').count()
        low_stock_products = Product.objects.filter(stock_quantity__lt=10, is_active=True).count()
        
        # Recent orders
        recent_orders = Order.objects.order_by('-created_at')[:5]
        
        return Response({
            "total_orders": total_orders,
            "total_sales": total_sales,
            "pending_orders": pending_orders,
            "low_stock_count": low_stock_products,
        })
