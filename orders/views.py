import decimal
from rest_framework import viewsets, permissions as drf_permissions, status, decorators
from rest_framework.response import Response
from .models import Order, OrderItem
from .serializers import OrderSerializer
from invoices.models import Invoice
from django.db import transaction
from pharmacies.models import Pharmacy
from rest_framework import serializers
from accounts.permissions import IsAdminUser

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from datetime import timedelta
from django.utils import timezone
from products.models import Product

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [drf_permissions.IsAuthenticated]

    @decorators.action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def summary(self, request):
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        # General Stats
        stats = Order.objects.exclude(status='rejected').aggregate(
            total_sales = Sum('total_amount') or 0,
            total_collections = Sum('paid_amount') or 0,
            order_count = Count('id')
        )
        
        # Sales Trend (Last 30 days)
        trend = Order.objects.filter(
            created_at__date__gte=thirty_days_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            sales=Sum('total_amount'),
            collections=Sum('paid_amount')
        ).order_by('date')
        
        # Top Pharmacies by Sales
        top_pharmacies = Order.objects.values(
            'pharmacy__pharmacy_name'
        ).annotate(
            total=Sum('total_amount')
        ).order_by('-total')[:5]
        
        return Response({
            "metrics": stats,
            "trend": list(trend),
            "top_pharmacies": list(top_pharmacies)
        })

    @decorators.action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def stock_requirements(self, request):
        # Calculate requirements based on pending/approved/processing/shipped orders
        active_statuses = ['pending', 'approved', 'processing', 'shipped']
        
        # Aggregate requirement per product
        requirements = OrderItem.objects.filter(
            order__status__in=active_statuses
        ).values('product').annotate(
            required_qty=Sum('quantity')
        )
        
        req_dict = {r['product']: r['required_qty'] for r in requirements}
        
        products = Product.objects.filter(is_active=True)
        report = []
        
        for p in products:
            required = req_dict.get(p.id, 0)
            in_hand = p.stock_quantity
            # If in_hand is negative (e.g. -5), it means we owe 5 from previous deliveries.
            # But usually we want to see physical stock.
            shortfall = max(0, required - in_hand)
            
            # Only show items that are required for active orders OR have negative stock (backorders)
            if required > 0 or in_hand < 0:
                report.append({
                    "id": p.id,
                    "name": p.name,
                    "in_hand": in_hand,
                    "required": required,
                    "shortfall": shortfall,
                    "to_purchase": shortfall
                })
        
        return Response(report)

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.all().select_related('pharmacy').prefetch_related('items__product')
        if user.role == 'admin':
            return queryset.order_by('-created_at')
        return queryset.filter(pharmacy=user.pharmacy).order_by('-created_at')

    def perform_create(self, serializer):
        # High-assurance order fulfillment
        if self.request.user.role == 'admin':
            pharmacy_id = self.request.data.get('pharmacy')
            if pharmacy_id:
                try:
                    pharmacy = Pharmacy.objects.get(id=pharmacy_id)
                    serializer.save(pharmacy=pharmacy)
                    return
                except Pharmacy.DoesNotExist:
                    raise serializers.ValidationError({"pharmacy": "Requested pharmacy not found"})
        
        # Standard pharmacy user flow
        user_pharmacy = getattr(self.request.user, 'pharmacy', None)
        if user_pharmacy:
            serializer.save(pharmacy=user_pharmacy)
        else:
            raise serializers.ValidationError({"error": "Admin account requires explicit pharmacy selection. Store accounts must have a linked pharmacy."})

    @decorators.action(detail=True, methods=['put'], permission_classes=[IsAdminUser])
    def record_payment(self, request, pk=None):
        order = self.get_object()
        payment_amount = request.data.get('amount', 0)
        try:
            payment_amount = float(payment_amount)
        except ValueError:
            return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)
            
        order.paid_amount += decimal.Decimal(str(payment_amount))
        
        if order.paid_amount >= order.total_amount:
            order.payment_status = 'paid'
        elif order.paid_amount > 0:
            order.payment_status = 'partial'
        else:
            order.payment_status = 'unpaid'
            
        order.save()
        return Response({
            "status": "Payment recorded",
            "paid_amount": order.paid_amount,
            "payment_status": order.payment_status
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Check if user is allowed to edit
        if request.user.role != 'admin' and instance.status != 'pending':
            return Response({"error": "Only pending orders can be modified"}, status=status.HTTP_400_BAD_REQUEST)
            
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @decorators.action(detail=True, methods=['put'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        order = self.get_object()
        if order.status != 'pending':
            return Response({"error": "Only pending orders can be approved"}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            order.status = 'approved'
            order.save()
            
            # Auto-generate Invoice
            Invoice.objects.get_or_create(order=order)
            
        return Response({"status": "Order approved and stock updated, invoice generated."})

    @decorators.action(detail=True, methods=['put'], permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = order.status
        order.status = new_status
        
        # Only deduct stock when delivered AND stock hasn't been deducted yet
        if new_status == 'delivered' and not order.stock_deducted:
            with transaction.atomic():
                # Reduce stock now that it's physically delivered
                for item in order.items.all():
                    item.product.stock_quantity -= item.quantity
                    item.product.save()
                order.stock_deducted = True
                order.save()
        else:
            order.save()
            
        return Response({"status": f"Order status updated to {new_status}"})
