from rest_framework import serializers
from .models import Order, OrderItem
from products.models import Product
from products.serializers import ProductSerializer
from pharmacies.models import Pharmacy

class OrderItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_details', 'quantity', 'free_qty', 'unit_price', 'gst_rate', 'total_price')
        read_only_fields = ('unit_price', 'total_price', 'gst_rate')

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    pharmacy = serializers.PrimaryKeyRelatedField(queryset=Pharmacy.objects.all(), required=False)
    pharmacy_name = serializers.ReadOnlyField(source='pharmacy.pharmacy_name')
    pharmacy_details = serializers.SerializerMethodField()
    balance_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'pharmacy', 'pharmacy_name', 'pharmacy_details',
            'status', 'total_amount', 'paid_amount', 'balance_amount', 'payment_status', 'items', 
            'salesman_name', 'terms', 'delivery_type',
            'created_at', 'updated_at'
        )
        read_only_fields = ('order_number', 'total_amount', 'status', 'balance_amount')

    def get_balance_amount(self, obj):
        from decimal import Decimal
        total = Decimal(str(obj.total_amount or 0))
        paid = Decimal(str(obj.paid_amount or 0))
        return total - paid

    def get_pharmacy_details(self, obj):
        from pharmacies.serializers import PharmacySerializer
        if obj.pharmacy:
            return PharmacySerializer(obj.pharmacy).data
        return None

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        self._process_items(order, items_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            # Re-process items: delete old ones and add new ones
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
            
            # Stock check removed to allow backordering as requested
            
            unit_price = product.selling_price
            gst_rate = product.gst_rate
            total_price = unit_price * quantity
            
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                free_qty=free_qty,
                unit_price=unit_price,
                gst_rate=gst_rate,
                total_price=total_price
            )
            total_amount += total_price
        
        order.total_amount = total_amount
        order.save()
