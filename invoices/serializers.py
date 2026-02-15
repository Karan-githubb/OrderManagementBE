from rest_framework import serializers
from .models import Invoice
from orders.serializers import OrderSerializer

class InvoiceSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    
    class Meta:
        model = Invoice
        fields = ('id', 'invoice_number', 'order', 'pdf_file', 'created_at')
