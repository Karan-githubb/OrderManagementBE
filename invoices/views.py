import os
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from weasyprint import HTML
from .models import Invoice
from .serializers import InvoiceSerializer

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Invoice.objects.all().order_by('-created_at')
        return Invoice.objects.filter(order__pharmacy=user.pharmacy).order_by('-created_at')

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        invoice = self.get_object()
        
        # Check if PDF already exists
        # For MVP, we generate on the fly or check if file exists
        
        template = get_template('invoices/invoice_template.html')
        html_content = template.render({'invoice': invoice})
        
        # Create PDF
        pdf_file = HTML(string=html_content, base_url=request.build_absolute_uri()).write_pdf()
        
        # For simplicity in MVP, we return it directly as response
        # Optionally save it to invoice.pdf_file.save(...)
        
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        return response
