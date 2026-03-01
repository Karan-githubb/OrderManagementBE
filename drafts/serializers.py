from rest_framework import serializers
from products.serializers import ProductSerializer
from .models import DraftOrder, DraftOrderItem


class DraftOrderItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = DraftOrderItem
        fields = ('id', 'product', 'product_details', 'quantity', 'unit_price', 'discount_amount')
        read_only_fields = ('unit_price',)


class DraftOrderSerializer(serializers.ModelSerializer):
    items = DraftOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = DraftOrder
        fields = ('id', 'items', 'created_at', 'updated_at')


class DraftOrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DraftOrderItem
        fields = ('product', 'quantity')
