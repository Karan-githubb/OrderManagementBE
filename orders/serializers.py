from rest_framework import serializers
from .models import Order, OrderItem, OrderItemAllocation, Dispatch
from products.models import Product, StockBatch
from products.serializers import ProductSerializer
from pharmacies.models import Pharmacy


class DispatchSerializer(serializers.ModelSerializer):
    total_value = serializers.SerializerMethodField()

    class Meta:
        model = Dispatch
        fields = ('id', 'dispatched_at', 'total_value')

    def get_total_value(self, obj):
        return str(obj.total_value())


class BulkDispatchItemSerializer(serializers.Serializer):
    order_item = serializers.PrimaryKeyRelatedField(queryset=OrderItem.objects.all())
    stock_batch = serializers.PrimaryKeyRelatedField(queryset=StockBatch.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class BulkDispatchSerializer(serializers.Serializer):
    allocations = BulkDispatchItemSerializer(many=True)

    def validate_allocations(self, value):
        if not value:
            raise serializers.ValidationError('At least one allocation is required.')
        return value


class OrderItemAllocationSerializer(serializers.ModelSerializer):
    batch_number = serializers.ReadOnlyField(source='stock_batch.batch_number')
    expiry_date = serializers.ReadOnlyField(source='stock_batch.expiry_date')

    class Meta:
        model = OrderItemAllocation
        fields = ('id', 'order_item', 'stock_batch', 'batch_number', 'expiry_date', 'quantity', 'dispatch', 'created_at')
        read_only_fields = ('created_at',)


class OrderItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    dispatched_quantity = serializers.ReadOnlyField()
    remaining_quantity = serializers.ReadOnlyField()
    allocations = OrderItemAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            'id', 'product', 'product_details', 'quantity', 'free_qty',
            'dispatched_quantity', 'remaining_quantity', 'allocations',
            'unit_price', 'discount_amount', 'gst_rate', 'total_price', 'is_void'
        )
        read_only_fields = ('total_price',)  # unit_price, gst_rate writable for admin order edit

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, required=False)
    dispatches = DispatchSerializer(many=True, read_only=True)
    pharmacy = serializers.PrimaryKeyRelatedField(queryset=Pharmacy.objects.all(), required=False)
    pharmacy_name = serializers.ReadOnlyField(source='pharmacy.pharmacy_name')
    pharmacy_details = serializers.SerializerMethodField()
    balance_amount = serializers.SerializerMethodField()
    dispatched_amount = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'pharmacy', 'pharmacy_name', 'pharmacy_details',
            'status', 'total_amount', 'paid_amount', 'balance_amount', 'payment_status',
            'dispatched_amount', 'outstanding_amount', 'is_void', 'items', 'dispatches',
            'salesman_name', 'terms', 'delivery_type',
            'created_at', 'updated_at'
        )
        read_only_fields = ('order_number', 'total_amount', 'status', 'balance_amount', 'dispatched_amount', 'outstanding_amount')

    def get_balance_amount(self, obj):
        from decimal import Decimal
        total = Decimal(str(obj.total_amount or 0))
        paid = Decimal(str(obj.paid_amount or 0))
        return total - paid

    def get_dispatched_amount(self, obj):
        return obj.dispatched_amount()

    def get_outstanding_amount(self, obj):
        """Amount still to collect: dispatched value minus already paid. Payment is only on dispatched."""
        from decimal import Decimal
        dispatched = obj.dispatched_amount()
        paid = Decimal(str(obj.paid_amount or 0))
        return max(Decimal('0'), dispatched - paid)

    def get_pharmacy_details(self, obj):
        from pharmacies.serializers import PharmacySerializer
        if obj.pharmacy:
            return PharmacySerializer(obj.pharmacy).data
        return None

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        order = Order.objects.create(**validated_data)
        if items_data:
            self._process_items(order, items_data)
        return order
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        # Update order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            # Only allow replacing items when order has no dispatch (allocations)
            if OrderItemAllocation.objects.filter(order_item__order=instance).exists():
                raise serializers.ValidationError(
                    {'items': 'Cannot edit order lines once dispatch has started. Order has allocated items.'}
                )
            instance.items.all().delete()
            self._process_items(instance, items_data)

        return instance

    def _process_items(self, order, items_data):
        from decimal import Decimal
        total_amount = Decimal('0')
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            free_qty = item_data.get('free_qty', 0)
            discount_amount = Decimal(str(item_data.get('discount_amount', 0)))
            # Admin edit: allow unit_price and gst_rate override; else use product defaults
            unit_price = item_data.get('unit_price')
            if unit_price is None:
                unit_price = product.selling_price
            else:
                unit_price = Decimal(str(unit_price))
            gst_rate = item_data.get('gst_rate')
            if gst_rate is None:
                gst_rate = product.gst_rate
            else:
                gst_rate = Decimal(str(gst_rate))
            total_price = unit_price * quantity - discount_amount

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                free_qty=free_qty,
                unit_price=unit_price,
                discount_amount=discount_amount,
                gst_rate=gst_rate,
                total_price=total_price
            )
            total_amount += total_price

        order.total_amount = total_amount
        order.save()
