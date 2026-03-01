from rest_framework import serializers
from .models import Invoice, CompanyProfile
from orders.serializers import OrderSerializer

class InvoiceSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)

    class Meta:
        model = Invoice
        fields = ('id', 'invoice_number', 'order', 'pdf_file', 'created_at')


class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = ('id', 'company_name', 'address', 'gst_number', 'license_number', 'phone', 'email')
