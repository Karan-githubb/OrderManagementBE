from decimal import Decimal
from rest_framework import status, permissions as drf_permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin
from pharmacies.models import Pharmacy
from products.models import Product
from orders.models import Order, OrderItem
from orders.serializers import OrderSerializer

from .models import DraftOrder, DraftOrderItem
from .serializers import DraftOrderSerializer, DraftOrderItemSerializer, DraftOrderItemCreateSerializer


def get_pharmacy_for_submit(request):
    """Resolve pharmacy at submit: pharmacy user -> their pharmacy; admin -> request.data."""
    user = request.user
    if user.role == 'pharmacy' and getattr(user, 'pharmacy', None):
        return user.pharmacy
    if user.role == 'admin':
        pharmacy_id = request.data.get('pharmacy')
        if pharmacy_id:
            try:
                return Pharmacy.objects.get(id=pharmacy_id)
            except Pharmacy.DoesNotExist:
                pass
    return None


def get_or_create_draft(user):
    draft, _ = DraftOrder.objects.get_or_create(user=user)
    return draft


class DraftViewSet(GenericViewSet):
    """GET mine: return current user's draft. POST submit: create order and clear draft."""
    permission_classes = [drf_permissions.IsAuthenticated]
    serializer_class = DraftOrderSerializer

    def list(self, request, *args, **kwargs):
        return self.mine(request)

    @action(detail=False, methods=['get'], url_path='mine')
    def mine(self, request):
        draft = DraftOrder.objects.filter(user=request.user).first()
        if not draft:
            return Response({'id': None, 'items': [], 'created_at': None, 'updated_at': None})
        serializer = DraftOrderSerializer(draft)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='submit')
    def submit(self, request):
        pharmacy = get_pharmacy_for_submit(request)
        if not pharmacy:
            return Response(
                {'detail': 'Pharmacy required. Admin must send pharmacy in body.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        draft = DraftOrder.objects.filter(user=request.user).first()
        if not draft or not draft.items.exists():
            return Response({'detail': 'No draft or draft is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        for di in draft.items.all():
            if not getattr(di.product, 'is_active', True):
                return Response(
                    {'detail': f'Product "{di.product.name}" is inactive and cannot be ordered. Remove it from the requisition.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        items_data = []
        for di in draft.items.all():
            items_data.append({
                'product': di.product,
                'quantity': di.quantity,
                'discount_amount': di.discount_amount,
            })
        order = Order.objects.create(pharmacy=pharmacy)
        total_amount = Decimal('0')
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            discount_amount = item_data['discount_amount']
            unit_price = product.selling_price
            gst_rate = product.gst_rate
            total_price = unit_price * quantity - discount_amount
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                discount_amount=discount_amount,
                gst_rate=gst_rate,
                total_price=total_price,
            )
            total_amount += total_price
        order.total_amount = total_amount
        order.save()

        draft.items.all().delete()
        draft.delete()

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DraftOrderItemViewSet(GenericViewSet, RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin):
    """CRUD for draft items. Each user has their own draft."""
    permission_classes = [drf_permissions.IsAuthenticated]
    serializer_class = DraftOrderItemSerializer

    def get_queryset(self):
        draft = DraftOrder.objects.filter(user=self.request.user).first()
        if not draft:
            return DraftOrderItem.objects.none()
        return DraftOrderItem.objects.filter(draft_order=draft)

    def get_draft(self, request):
        return get_or_create_draft(request.user)

    def create(self, request, *args, **kwargs):
        draft = self.get_draft(request)
        ser = DraftOrderItemCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        product = ser.validated_data['product']
        quantity = ser.validated_data['quantity']

        if not getattr(product, 'is_active', True):
            return Response(
                {'detail': 'This product is inactive and cannot be ordered.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        percent = getattr(product, 'default_discount_percent', None) or Decimal('0')
        line_subtotal = product.selling_price * quantity
        line_discount = line_subtotal * (percent / Decimal('100'))

        item, created = DraftOrderItem.objects.get_or_create(
            draft_order=draft,
            product=product,
            defaults={
                'quantity': quantity,
                'unit_price': product.selling_price,
                'discount_amount': line_discount,
            }
        )
        if not created:
            item.quantity += quantity
            item.discount_amount = (item.unit_price * item.quantity) * (percent / Decimal('100'))
            item.save()
        out_ser = DraftOrderItemSerializer(item)
        return Response(out_ser.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        draft = self.get_draft(request)
        if instance.draft_order_id != draft.id:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if 'quantity' in request.data:
            instance.quantity = int(request.data['quantity'])
            percent = getattr(instance.product, 'default_discount_percent', None) or Decimal('0')
            instance.discount_amount = (instance.unit_price * instance.quantity) * (percent / Decimal('100'))
        instance.save()
        return Response(DraftOrderItemSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        draft = self.get_draft(request)
        if instance.draft_order_id != draft.id:
            return Response(status=status.HTTP_403_FORBIDDEN)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
