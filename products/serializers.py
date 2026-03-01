from rest_framework import serializers
from .models import Product, Category, Purchase, PurchaseItem, StockBatch


class StockBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockBatch
        fields = ['id', 'batch_number', 'expiry_date', 'quantity', 'received_date']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    image_url = serializers.SerializerMethodField()
    batches = StockBatchSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name', 'description', 'mrp', 'selling_price',
            'stock_quantity', 'pack_size', 'unit', 'default_discount_percent', 'gst_rate', 'image_url',
            'is_active', 'created_at', 'batches'
        ]
        read_only_fields = ['stock_quantity']  # Stock only via purchase approval and dispatch

    def get_image_url(self, obj):
        if obj.image_url:
            return obj.image_url
        return "https://images.unsplash.com/photo-1583912267550-d44d7a12517a?auto=format&fit=crop&q=80&w=400"

class PurchaseItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = PurchaseItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price', 'batch_number', 'expiry_date']
        read_only_fields = ['id', 'product_name']


class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = '__all__'

    def create(self, validated_data):
        validated_data.pop('items', None)
        items_data = self.context.get('request').data.get('items', [])
        purchase = Purchase.objects.create(**validated_data)
        received = purchase.purchase_date

        for item_data in items_data:
            product_id = item_data.get('product')
            quantity = int(item_data.get('quantity') or 0)
            unit_price = item_data.get('unit_price')
            batch_number = item_data.get('batch_number') or ''
            expiry_date = item_data.get('expiry_date')

            if not product_id or not quantity or unit_price is None:
                continue

            try:
                product = Product.objects.get(id=product_id)
                PurchaseItem.objects.create(
                    purchase=purchase,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    batch_number=batch_number or None,
                    expiry_date=expiry_date
                )
                # Stock is added only after purchase approval (see approve action)
            except Product.DoesNotExist:
                continue

        return purchase
