from rest_framework import viewsets, permissions as drf_permissions, filters, status, decorators
from rest_framework.response import Response
from django.db import transaction
from .models import Product, Category, Purchase, PurchaseItem, StockBatch
from .serializers import ProductSerializer, CategorySerializer, PurchaseSerializer, StockBatchSerializer
from accounts.permissions import IsAdminUser

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [drf_permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'category__name', 'description']
    pagination_class = None  # Admin inventory fetches all products; table paginates client-side

    def get_queryset(self):
        queryset = Product.objects.all().order_by('-id')
        if self.request.user.is_authenticated and self.request.user.role == 'admin':
            return queryset
        return queryset.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [drf_permissions.AllowAny]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all().order_by('-created_at')
    serializer_class = PurchaseSerializer
    permission_classes = [IsAdminUser]

    @decorators.action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        purchase = self.get_object()
        if purchase.status == 'approved':
            return Response({'detail': 'Already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        received = purchase.purchase_date
        with transaction.atomic():
            for item in purchase.items.all():
                if not item.batch_number or not item.expiry_date:
                    continue
                # Same batch number + same expiry = add to existing lot. Same batch number + different expiry = new lot.
                batch, created = StockBatch.objects.get_or_create(
                    product=item.product,
                    batch_number=item.batch_number,
                    expiry_date=item.expiry_date,
                    defaults={'quantity': 0, 'received_date': received}
                )
                batch.quantity += item.quantity
                batch.received_date = received
                batch.save()
                item.product.stock_quantity += item.quantity
                item.product.save()
            purchase.status = 'approved'
            purchase.save()
        return Response({'status': 'approved', 'detail': 'Stock added to inventory.'})


class StockBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """List and manage batches. Use write_off to zero out expired stock."""
    queryset = StockBatch.objects.all().select_related('product').order_by('product__name', 'expiry_date')
    serializer_class = StockBatchSerializer
    permission_classes = [IsAdminUser]

    @decorators.action(detail=True, methods=['post'], url_path='write-off')
    def write_off(self, request, pk=None):
        """Zero out batch quantity (e.g. expired/damaged). Deducts from product stock."""
        batch = self.get_object()
        if batch.quantity <= 0:
            return Response({'detail': 'Batch already has zero quantity.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            qty = batch.quantity
            batch.quantity = 0
            batch.save()
            batch.product.stock_quantity -= qty
            batch.product.save()
        return Response({'status': 'written off', 'quantity_zeroed': qty})
