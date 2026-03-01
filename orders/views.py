import decimal
from rest_framework import viewsets, permissions as drf_permissions, status, decorators
from rest_framework.response import Response
from .models import Order, OrderItem, OrderItemAllocation, Dispatch
from .serializers import OrderSerializer, OrderItemAllocationSerializer, BulkDispatchSerializer, DispatchSerializer
from invoices.models import Invoice
from django.db import transaction
from pharmacies.models import Pharmacy
from rest_framework import serializers
from accounts.permissions import IsAdminUser

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncWeek
from datetime import timedelta
from django.utils import timezone
from products.models import Product
from products.models import StockBatch

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [drf_permissions.IsAuthenticated]

    @decorators.action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def summary(self, request):
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        group = request.query_params.get('group', 'day')  # day | week | month

        base_qs = Order.objects.exclude(status='rejected')
        if start_date:
            try:
                from datetime import datetime
                start_d = datetime.strptime(start_date, '%Y-%m-%d').date()
                base_qs = base_qs.filter(created_at__date__gte=start_d)
            except ValueError:
                pass
        if end_date:
            try:
                from datetime import datetime
                end_d = datetime.strptime(end_date, '%Y-%m-%d').date()
                base_qs = base_qs.filter(created_at__date__lte=end_d)
            except ValueError:
                pass

        # If no date range given, default to last 30 days for trend only; stats remain all-time
        trend_qs = base_qs
        if not start_date and not end_date:
            trend_qs = base_qs.filter(created_at__date__gte=thirty_days_ago)

        # General Stats (over filtered range)
        stats = base_qs.aggregate(
            total_sales=Sum('total_amount') or 0,
            total_collections=Sum('paid_amount') or 0,
            order_count=Count('id')
        )

        # Sales Trend
        if group == 'month':
            daily = list(trend_qs.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                sales=Sum('total_amount'),
                collections=Sum('paid_amount')
            ).order_by('date'))
            from collections import defaultdict
            by_month = defaultdict(lambda: {'sales': 0, 'collections': 0})
            for row in daily:
                key = row['date'].replace(day=1) if row.get('date') else None
                if key:
                    by_month[key]['sales'] += float(row.get('sales') or 0)
                    by_month[key]['collections'] += float(row.get('collections') or 0)
            trend = [{'date': k, 'sales': v['sales'], 'collections': v['collections']} for k, v in sorted(by_month.items())]
        elif group == 'week':
            trend = list(trend_qs.annotate(
                date=TruncWeek('created_at')
            ).values('date').annotate(
                sales=Sum('total_amount'),
                collections=Sum('paid_amount')
            ).order_by('date'))
        else:
            trend = list(trend_qs.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                sales=Sum('total_amount'),
                collections=Sum('paid_amount')
            ).order_by('date'))

        # Top Pharmacies by Sales (with collections and order count), same date filter
        top_pharmacies = list(base_qs.values(
            'pharmacy', 'pharmacy__pharmacy_name'
        ).annotate(
            total=Sum('total_amount'),
            paid=Sum('paid_amount'),
            order_count=Count('id')
        ).order_by('-total')[:10])
        # Ensure keys exist for frontend
        for p in top_pharmacies:
            p.setdefault('pharmacy__pharmacy_name', '')
            p.setdefault('paid', 0)
            p.setdefault('order_count', 0)

        return Response({
            "metrics": stats,
            "trend": trend,
            "top_pharmacies": top_pharmacies
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
        queryset = Order.objects.all().select_related('pharmacy').prefetch_related(
            'items__product', 'items__allocations__stock_batch', 'dispatches'
        )
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
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)
        if payment_amount <= 0:
            return Response({"error": "Amount must be greater than 0."}, status=status.HTTP_400_BAD_REQUEST)

        dispatched = order.dispatched_amount()
        new_paid = order.paid_amount + decimal.Decimal(str(payment_amount))
        if new_paid > dispatched:
            return Response({
                "error": f"Cannot collect more than dispatched value. Dispatched: ₹{dispatched:.2f}, already paid: ₹{order.paid_amount:.2f}. Maximum you can record: ₹{(dispatched - order.paid_amount):.2f}."
            }, status=status.HTTP_400_BAD_REQUEST)

        order.paid_amount = new_paid
        if order.paid_amount >= dispatched:
            order.payment_status = 'paid'
        elif order.paid_amount > 0:
            order.payment_status = 'partial'
        else:
            order.payment_status = 'unpaid'
        order.save()
        return Response({
            "status": "Payment recorded",
            "paid_amount": order.paid_amount,
            "payment_status": order.payment_status,
            "dispatched_amount": str(dispatched),
            "outstanding_amount": str(max(decimal.Decimal('0'), dispatched - order.paid_amount)),
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
        
        order.status = new_status
        order.save()
        # Stock is deducted only when creating allocations (dispatch), not on status change.
        return Response({"status": f"Order status updated to {new_status}"})

    @decorators.action(detail=True, methods=['get'], url_path='items/(?P<item_id>[^/.]+)/available-batches', permission_classes=[IsAdminUser])
    def available_batches(self, request, pk=None, item_id=None):
        """List batches with available qty for an order line (for dispatch selection)."""
        order = self.get_object()
        try:
            order_item = order.items.get(pk=item_id)
        except OrderItem.DoesNotExist:
            return Response({'detail': 'Order item not found.'}, status=status.HTTP_404_NOT_FOUND)
        from django.utils import timezone
        today = timezone.now().date()
        batches = StockBatch.objects.filter(
            product=order_item.product,
            quantity__gt=0,
            expiry_date__gte=today
        ).order_by('expiry_date')
        data = [{'id': b.id, 'batch_number': b.batch_number, 'expiry_date': b.expiry_date, 'quantity': b.quantity} for b in batches]
        return Response(data)

    @decorators.action(detail=True, methods=['post'], url_path='dispatches', permission_classes=[IsAdminUser])
    def create_dispatch(self, request, pk=None):
        """Create one dispatch event with multiple allocations. Each save = one Dispatch = one bill."""
        order = self.get_object()
        if order.is_void:
            return Response({'detail': 'Cannot dispatch a voided order.'}, status=status.HTTP_400_BAD_REQUEST)
        ser = BulkDispatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        allocations_data = ser.validated_data['allocations']
        with transaction.atomic():
            dispatch = Dispatch.objects.create(order=order)
            created = []
            for row in allocations_data:
                order_item = row['order_item']
                if order_item.order_id != order.id:
                    raise serializers.ValidationError({'allocations': f'Order item {order_item.id} does not belong to this order.'})
                stock_batch = row['stock_batch']
                qty = row['quantity']
                if stock_batch.product_id != order_item.product_id:
                    raise serializers.ValidationError({'allocations': f'Batch does not belong to product for order item {order_item.id}.'})
                remaining = order_item.remaining_quantity
                if remaining <= 0:
                    raise serializers.ValidationError({'allocations': f'No remaining quantity to dispatch for order item {order_item.id}.'})
                available = stock_batch.quantity
                if qty <= 0 or qty > min(remaining, available):
                    raise serializers.ValidationError({'allocations': f'Quantity for order item {order_item.id} must be 1–{min(remaining, available)}.'})
                allocation = OrderItemAllocation.objects.create(
                    order_item=order_item, stock_batch=stock_batch, quantity=qty, dispatch=dispatch
                )
                stock_batch.quantity -= qty
                stock_batch.save(update_fields=['quantity'])
                order_item.product.stock_quantity -= qty
                order_item.product.save(update_fields=['stock_quantity'])
                created.append(allocation)
        return Response({
            'dispatch': DispatchSerializer(dispatch).data,
            'allocations': OrderItemAllocationSerializer(created, many=True).data,
        }, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=['post'], url_path='allocations', permission_classes=[IsAdminUser])
    def create_allocation(self, request, pk=None):
        """Legacy: single allocation (no Dispatch). Prefer POST /dispatches/ for multiple lines."""
        order = self.get_object()
        ser = OrderItemAllocationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        order_item_id = ser.validated_data['order_item'].id
        try:
            order_item = order.items.get(pk=order_item_id)
        except OrderItem.DoesNotExist:
            return Response({'detail': 'Order item not found for this order.'}, status=status.HTTP_400_BAD_REQUEST)
        stock_batch = ser.validated_data['stock_batch']
        qty = ser.validated_data['quantity']
        if stock_batch.product_id != order_item.product_id:
            return Response({'detail': 'Batch does not belong to this product.'}, status=status.HTTP_400_BAD_REQUEST)
        remaining = order_item.remaining_quantity
        if remaining <= 0:
            return Response({'detail': 'No remaining quantity to dispatch for this line.'}, status=status.HTTP_400_BAD_REQUEST)
        available = stock_batch.quantity
        if qty <= 0 or qty > min(remaining, available):
            return Response({'detail': f'Quantity must be between 1 and {min(remaining, available)}.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            allocation = OrderItemAllocation.objects.create(order_item=order_item, stock_batch=stock_batch, quantity=qty)
            stock_batch.quantity -= qty
            stock_batch.save()
            order_item.product.stock_quantity -= qty
            order_item.product.save()
        return Response(OrderItemAllocationSerializer(allocation).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=['post'], url_path='void', permission_classes=[IsAdminUser])
    def void_order(self, request, pk=None):
        """Void the entire order. Sets order and all its items as voided."""
        order = self.get_object()
        if order.is_void:
            return Response({'detail': 'Order is already voided.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            order.is_void = True
            order.items.update(is_void=True)
            order.total_amount = 0
            order.save(update_fields=['is_void', 'total_amount'])
        return Response({'status': 'Order voided.', 'order_id': order.id})

    @decorators.action(detail=True, methods=['post'], url_path='items/(?P<item_id>[^/.]+)/void', permission_classes=[IsAdminUser])
    def void_order_item(self, request, pk=None, item_id=None):
        """Void a single order line. Recalculates order total from non-void items."""
        order = self.get_object()
        if order.is_void:
            return Response({'detail': 'Order is already voided.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            order_item = order.items.get(pk=item_id)
        except OrderItem.DoesNotExist:
            return Response({'detail': 'Order item not found.'}, status=status.HTTP_404_NOT_FOUND)
        if order_item.is_void:
            return Response({'detail': 'Item is already voided.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            order_item.is_void = True
            order_item.save(update_fields=['is_void'])
            from decimal import Decimal
            new_total = order.items.filter(is_void=False).aggregate(
                total=Sum('total_price')
            )['total'] or Decimal('0')
            order.total_amount = new_total
            order.save()
        return Response({'status': 'Order item voided.', 'order_total': str(order.total_amount)})
