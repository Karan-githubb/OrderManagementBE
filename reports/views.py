from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from accounts.permissions import IsAdminUser, IsPharmacyUser
from orders.models import Order, OrderItem, OrderItemAllocation
from products.models import Product, StockBatch, Purchase, PurchaseItem
from pharmacies.models import Pharmacy
from invoices.models import Invoice


def _parse_date_range(request):
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    start_d = end_d = None
    if start_date:
        try:
            start_d = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    if end_date:
        try:
            end_d = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    return start_d, end_d


class AdminDashboardStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        total_orders = Order.objects.count()
        total_sales = Order.objects.filter(status='delivered').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        pending_orders = Order.objects.filter(status='pending').count()
        low_stock_products = Product.objects.filter(stock_quantity__lt=10, is_active=True).count()
        recent_orders = Order.objects.order_by('-created_at')[:5]
        return Response({
            "total_orders": total_orders,
            "total_sales": total_sales,
            "pending_orders": pending_orders,
            "low_stock_count": low_stock_products,
        })


class SalesByProductReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_d, end_d = _parse_date_range(request)
        qs = OrderItemAllocation.objects.filter(
            order_item__order__status__in=['approved', 'processing', 'shipped', 'delivered']
        ).select_related('order_item__order', 'order_item__product')
        if start_d:
            qs = qs.filter(order_item__order__created_at__date__gte=start_d)
        if end_d:
            qs = qs.filter(order_item__order__created_at__date__lte=end_d)
        from collections import defaultdict
        by_product = defaultdict(lambda: {'quantity': 0, 'value': Decimal('0'), 'name': None})
        for a in qs:
            pid = a.order_item.product_id
            qty = a.quantity
            price = a.order_item.unit_price or 0
            by_product[pid]['quantity'] += qty
            by_product[pid]['value'] += qty * price
            by_product[pid]['name'] = a.order_item.product.name if a.order_item.product_id else '—'
        report = [
            {'product_id': pid, 'product_name': data['name'] or '—', 'quantity': data['quantity'], 'value': float(data['value'])}
            for pid, data in by_product.items()
        ]
        report.sort(key=lambda x: -x['value'])
        return Response(report)


class OutstandingByStoreReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Dispatched per pharmacy: sum of (allocations.quantity * order_item.unit_price)
        allocations = OrderItemAllocation.objects.select_related(
            'order_item__order', 'order_item__order__pharmacy'
        ).filter(order_item__order__status__in=['approved', 'processing', 'shipped', 'delivered'])
        from collections import defaultdict
        dispatched_map = defaultdict(lambda: Decimal('0'))
        for a in allocations:
            pid = a.order_item.order.pharmacy_id
            if pid:
                dispatched_map[pid] += a.quantity * (a.order_item.unit_price or 0)
        dispatched_map = {k: float(v) for k, v in dispatched_map.items()}
        paid = Order.objects.values('pharmacy').annotate(paid=Sum('paid_amount'))
        paid_map = {r['pharmacy']: float(r['paid'] or 0) for r in paid}
        pharmacy_ids = set(dispatched_map) | set(paid_map)
        pharmacies = {p.id: p.pharmacy_name for p in Pharmacy.objects.filter(id__in=pharmacy_ids)}
        report = []
        for pid in pharmacy_ids:
            disp = dispatched_map.get(pid, 0)
            paid_amt = paid_map.get(pid, 0)
            report.append({
                'pharmacy_id': pid,
                'pharmacy_name': pharmacies.get(pid, '—'),
                'dispatched_amount': disp,
                'paid_amount': paid_amt,
                'outstanding': max(0, disp - paid_amt),
            })
        report.sort(key=lambda x: -x['outstanding'])
        return Response(report)


class CollectionsSummaryReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_d, end_d = _parse_date_range(request)
        qs = Order.objects.exclude(status='rejected')
        if start_d:
            qs = qs.filter(created_at__date__gte=start_d)
        if end_d:
            qs = qs.filter(created_at__date__lte=end_d)
        agg = qs.aggregate(
            total_collections=Sum('paid_amount'),
            order_count=Count('id'),
        )
        return Response({
            'total_collections': float(agg['total_collections'] or 0),
            'order_count': agg['order_count'] or 0,
        })


class StockExpiryReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        days = int(request.query_params.get('days', 90))
        today = timezone.now().date()
        end_date = today + timedelta(days=days)
        batches = StockBatch.objects.filter(
            quantity__gt=0,
            expiry_date__gte=today,
            expiry_date__lte=end_date
        ).select_related('product').order_by('expiry_date')
        report = [
            {
                'batch_id': b.id,
                'product_id': b.product_id,
                'product_name': b.product.name,
                'batch_number': b.batch_number,
                'expiry_date': str(b.expiry_date),
                'quantity': b.quantity,
                'days_until_expiry': (b.expiry_date - today).days,
            }
            for b in batches
        ]
        return Response(report)


class LowStockReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        threshold = int(request.query_params.get('threshold', 10))
        products = Product.objects.filter(
            is_active=True,
            stock_quantity__lt=threshold
        ).values('id', 'name', 'stock_quantity', 'category__name').order_by('stock_quantity')
        report = [
            {
                'product_id': p['id'],
                'product_name': p['name'],
                'category': p['category__name'] or '—',
                'stock_quantity': p['stock_quantity'],
            }
            for p in products
        ]
        return Response(report)


class StockRequirementsReport(APIView):
    """Re-expose stock requirements (in_hand, required, shortfall) for report UI."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from orders.views import OrderViewSet
        # Reuse logic: we need OrderViewSet.stock_requirements logic without the viewset
        active_statuses = ['pending', 'approved', 'processing', 'shipped']
        requirements = OrderItem.objects.filter(
            order__status__in=active_statuses
        ).values('product').annotate(required_qty=Sum('quantity'))
        req_dict = {r['product']: r['required_qty'] for r in requirements}
        products = Product.objects.filter(is_active=True)
        report = []
        for p in products:
            required = req_dict.get(p.id, 0)
            in_hand = p.stock_quantity
            shortfall = max(0, required - in_hand)
            if required > 0 or in_hand < 0:
                report.append({
                    'product_id': p.id,
                    'product_name': p.name,
                    'in_hand': in_hand,
                    'required': required,
                    'shortfall': shortfall,
                    'to_purchase': shortfall,
                })
        report.sort(key=lambda x: -x['shortfall'])
        return Response(report)


class CurrentStockSummaryReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        category_id = request.query_params.get('category_id')
        qs = Product.objects.filter(is_active=True).select_related('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
        qs = qs.values('id', 'name', 'stock_quantity', 'category__name').order_by('category__name', 'name')
        report = [
            {
                'product_id': p['id'],
                'product_name': p['name'],
                'category': p['category__name'] or '—',
                'stock_quantity': p['stock_quantity'],
            }
            for p in qs
        ]
        total_qty = sum(p['stock_quantity'] for p in report)
        return Response({'items': report, 'total_quantity': total_qty})


class StockValuationReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Use selling_price for valuation (simplest)
        products = Product.objects.filter(is_active=True)
        total = sum(float(p.stock_quantity * p.selling_price) for p in products)
        report = [
            {
                'product_id': p.id,
                'product_name': p.name,
                'stock_quantity': p.stock_quantity,
                'unit_price': float(p.selling_price),
                'value': float(p.stock_quantity * p.selling_price),
            }
            for p in products if p.stock_quantity > 0
        ]
        report.sort(key=lambda x: -x['value'])
        return Response({'items': report, 'total_valuation': total})


class PurchaseHistoryReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_d, end_d = _parse_date_range(request)
        status_filter = request.query_params.get('status')  # pending | approved
        supplier = request.query_params.get('supplier')
        qs = Purchase.objects.all().order_by('-created_at')
        if start_d:
            qs = qs.filter(purchase_date__gte=start_d)
        if end_d:
            qs = qs.filter(purchase_date__lte=end_d)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if supplier:
            qs = qs.filter(supplier_name__icontains=supplier)
        report = [
            {
                'id': p.id,
                'supplier_name': p.supplier_name,
                'purchase_date': str(p.purchase_date),
                'total_amount': float(p.total_amount),
                'status': p.status,
                'created_at': p.created_at.isoformat() if p.created_at else None,
            }
            for p in qs
        ]
        return Response(report)


class PurchaseByProductReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_d, end_d = _parse_date_range(request)
        qs = PurchaseItem.objects.filter(purchase__status='approved').select_related('product')
        if start_d:
            qs = qs.filter(purchase__purchase_date__gte=start_d)
        if end_d:
            qs = qs.filter(purchase__purchase_date__lte=end_d)
        from collections import defaultdict
        by_product = defaultdict(lambda: {'quantity': 0, 'value': Decimal('0'), 'name': None})
        for item in qs:
            pid = item.product_id
            by_product[pid]['quantity'] += item.quantity
            by_product[pid]['value'] += item.quantity * (item.unit_price or 0)
            by_product[pid]['name'] = item.product.name if item.product_id else '—'
        report = [
            {'product_id': pid, 'product_name': data['name'] or '—', 'quantity': data['quantity'], 'value': float(data['value'])}
            for pid, data in by_product.items()
        ]
        report.sort(key=lambda x: -x['value'])
        return Response(report)


class OrderStatusSummaryReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = Order.objects.values('status').annotate(count=Count('id')).order_by('-count')
        report = [{'status': r['status'], 'count': r['count']} for r in qs]
        return Response(report)


class FulfillmentReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        group_by = request.query_params.get('group_by', 'order')  # order | product
        if group_by == 'product':
            # Per product: total ordered vs total dispatched
            items = OrderItem.objects.filter(
                order__status__in=['approved', 'processing', 'shipped', 'delivered']
            ).values('product', 'product__name').annotate(
                ordered=Sum('quantity'),
            )
            # Dispatched per product from allocations
            disp = OrderItemAllocation.objects.filter(
                order_item__order__status__in=['approved', 'processing', 'shipped', 'delivered']
            ).values('order_item__product').annotate(dispatched=Sum('quantity'))
            disp_map = {r['order_item__product']: (r['dispatched'] or 0) for r in disp}
            report = []
            for r in items:
                prod_id = r['product']
                dispatched = disp_map.get(prod_id, 0)
                report.append({
                    'product_id': prod_id,
                    'product_name': r['product__name'] or '—',
                    'ordered': r['ordered'],
                    'dispatched': dispatched,
                    'remaining': r['ordered'] - dispatched,
                })
            report.sort(key=lambda x: -x['ordered'])
        else:
            # Per order
            orders = Order.objects.exclude(status__in=['pending', 'rejected']).prefetch_related('items')
            report = []
            for o in orders:
                total_ordered = sum(i.quantity for i in o.items.all())
                total_dispatched = sum(i.dispatched_quantity for i in o.items.all())
                report.append({
                    'order_id': o.id,
                    'order_number': o.order_number,
                    'pharmacy_name': o.pharmacy.pharmacy_name if o.pharmacy else '—',
                    'ordered': total_ordered,
                    'dispatched': total_dispatched,
                    'remaining': total_ordered - total_dispatched,
                })
            report.sort(key=lambda x: -x['ordered'])
        return Response(report)


class InvoiceListReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_d, end_d = _parse_date_range(request)
        qs = Invoice.objects.select_related('order').order_by('-created_at')
        if start_d:
            qs = qs.filter(created_at__date__gte=start_d)
        if end_d:
            qs = qs.filter(created_at__date__lte=end_d)
        report = [
            {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'order_id': inv.order_id,
                'order_number': inv.order.order_number if inv.order else '—',
                'created_at': inv.created_at.isoformat() if inv.created_at else None,
            }
            for inv in qs
        ]
        return Response(report)


class InvoicesGeneratedReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_d, end_d = _parse_date_range(request)
        qs = Invoice.objects.all()
        if start_d:
            qs = qs.filter(created_at__date__gte=start_d)
        if end_d:
            qs = qs.filter(created_at__date__lte=end_d)
        count = qs.count()
        return Response({'count': count})


class VoidReport(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        start_d, end_d = _parse_date_range(request)
        # Voided whole orders
        orders_qs = Order.objects.filter(is_void=True).select_related('pharmacy').order_by('-updated_at')
        if start_d:
            orders_qs = orders_qs.filter(updated_at__date__gte=start_d)
        if end_d:
            orders_qs = orders_qs.filter(updated_at__date__lte=end_d)
        voided_orders = [
            {
                'order_id': o.id,
                'order_number': o.order_number,
                'pharmacy_name': o.pharmacy.pharmacy_name if o.pharmacy else '—',
                'status': o.status,
                'total_amount': float(o.total_amount),
                'voided_at': o.updated_at.isoformat() if o.updated_at else None,
            }
            for o in orders_qs
        ]
        # Voided line items (order not fully voided)
        items_qs = OrderItem.objects.filter(is_void=True).select_related('order', 'order__pharmacy', 'product').order_by('-id')
        if start_d:
            items_qs = items_qs.filter(order__updated_at__date__gte=start_d)
        if end_d:
            items_qs = items_qs.filter(order__updated_at__date__lte=end_d)
        voided_items = [
            {
                'order_item_id': i.id,
                'order_id': i.order_id,
                'order_number': i.order.order_number if i.order else '—',
                'pharmacy_name': i.order.pharmacy.pharmacy_name if i.order and i.order.pharmacy else '—',
                'product_name': i.product.name if i.product_id else '—',
                'quantity': i.quantity,
                'total_price': float(i.total_price),
            }
            for i in items_qs
        ]
        return Response({
            'voided_orders': voided_orders,
            'voided_items': voided_items,
        })


class PharmacyOrderSummaryView(APIView):
    """Order status summary for the logged-in pharmacy only."""
    permission_classes = [IsPharmacyUser]

    def get(self, request):
        pharmacy = getattr(request.user, 'pharmacy', None)
        if not pharmacy:
            return Response([], status=200)
        qs = Order.objects.filter(pharmacy=pharmacy).values('status').annotate(count=Count('id')).order_by('-count')
        report = [{'status': r['status'], 'count': r['count']} for r in qs]
        return Response(report)


class PharmacyOutstandingView(APIView):
    """Outstanding (dispatched vs paid) for the logged-in pharmacy only."""
    permission_classes = [IsPharmacyUser]

    def get(self, request):
        pharmacy = getattr(request.user, 'pharmacy', None)
        if not pharmacy:
            return Response({'dispatched_amount': 0, 'paid_amount': 0, 'outstanding': 0})
        dispatched_result = OrderItemAllocation.objects.filter(
            order_item__order__pharmacy=pharmacy,
            order_item__order__status__in=['approved', 'processing', 'shipped', 'delivered']
        ).aggregate(total=Sum(F('quantity') * F('order_item__unit_price')))
        dispatched = dispatched_result['total'] or Decimal('0')
        paid = Order.objects.filter(pharmacy=pharmacy).aggregate(paid=Sum('paid_amount'))['paid'] or Decimal('0')
        outstanding = max(Decimal('0'), dispatched - paid)
        return Response({
            'dispatched_amount': float(dispatched),
            'paid_amount': float(paid),
            'outstanding': float(outstanding),
        })


class PharmacyInvoiceListView(APIView):
    """Invoice list for the logged-in pharmacy only."""
    permission_classes = [IsPharmacyUser]

    def get(self, request):
        pharmacy = getattr(request.user, 'pharmacy', None)
        if not pharmacy:
            return Response([])
        qs = Invoice.objects.filter(order__pharmacy=pharmacy).select_related('order').order_by('-created_at')[:50]
        report = [
            {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'order_id': inv.order_id,
                'order_number': inv.order.order_number if inv.order else '—',
                'created_at': inv.created_at.isoformat() if inv.created_at else None,
                'total_amount': float(inv.order.total_amount) if inv.order else 0,
            }
            for inv in qs
        ]
        return Response(report)
