from rest_framework import serializers
from .models import Product, Category, Purchase, PurchaseItem

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        if obj.image_url:
            return obj.image_url
        # Generic high-quality medical placeholder if no image exists
        return "https://images.unsplash.com/photo-1583912267550-d44d7a12517a?auto=format&fit=crop&q=80&w=400"

class PurchaseItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    
    class Meta:
        model = PurchaseItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price']
        read_only_fields = ['id', 'product_name']

class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Purchase
        fields = '__all__'

    def create(self, validated_data):
        # Remove items from validated_data if present
        validated_data.pop('items', None)
        
        # Get items from request data
        items_data = self.context.get('request').data.get('items', [])
        
        # Create the purchase
        purchase = Purchase.objects.create(**validated_data)
        
        # Process each item
        for item_data in items_data:
            product_id = item_data.get('product')
            quantity = item_data.get('quantity')
            unit_price = item_data.get('unit_price')
            
            if not all([product_id, quantity, unit_price]):
                continue
            
            try:
                product = Product.objects.get(id=product_id)
                PurchaseItem.objects.create(
                    purchase=purchase,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price
                )
                
                # Increase stock
                product.stock_quantity += int(quantity)
                product.save()
            except Product.DoesNotExist:
                continue
            
        return purchase
