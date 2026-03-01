import os
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from weasyprint import HTML
from accounts.permissions import IsAdminUser
from .models import Invoice, CompanyProfile
from .serializers import InvoiceSerializer, CompanyProfileSerializer

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Invoice.objects.select_related('order', 'order__pharmacy').prefetch_related(
            'order__items', 'order__items__product', 'order__items__allocations', 'order__items__allocations__stock_batch'
        ).order_by('-created_at')
        user = self.request.user
        if user.role != 'admin':
            qs = qs.filter(order__pharmacy=user.pharmacy)
        order_id = self.request.query_params.get('order')
        if order_id:
            qs = qs.filter(order_id=order_id)
        return qs

    def _get_company(self):
        return CompanyProfile.objects.first()

    def _build_dispatch_lines(self, order, dispatch_id=None, dispatch_date=None):
        """Build list of dispatched line rows. If dispatch_id is set, only that dispatch; else if dispatch_date (YYYY-MM-DD) is set, allocations from that date (legacy)."""
        from datetime import datetime
        lines = []
        date_filter = None
        if dispatch_date:
            try:
                date_filter = datetime.strptime(dispatch_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        for item in order.items.filter(is_void=False):
            qs = item.allocations.select_related('stock_batch').all()
            if dispatch_id is not None:
                qs = qs.filter(dispatch_id=dispatch_id)
            elif date_filter:
                qs = qs.filter(created_at__date=date_filter)
            for alloc in qs:
                batch = alloc.stock_batch
                lines.append({
                    'product_name': item.product.name,
                    'mrp': item.product.mrp,
                    'batch_number': batch.batch_number,
                    'expiry_date': batch.expiry_date,
                    'quantity': alloc.quantity,
                    'free_qty': 0,
                    'unit_price': item.unit_price,
                    'gst_rate': item.gst_rate,
                    'total_price': alloc.quantity * item.unit_price,
                })
        return lines

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        invoice = self.get_object()
        bill_type = request.query_params.get('bill_type', 'overall')  # 'overall' | 'dispatch'
        dispatch_id = request.query_params.get('dispatch_id')  # optional: specific Dispatch id for per-dispatch bill
        dispatch_date = request.query_params.get('dispatch_date')  # optional YYYY-MM-DD (legacy, when no dispatch_id)
        company = self._get_company()
        order = invoice.order
        if bill_type == 'dispatch':
            if dispatch_id:
                try:
                    dispatch_id = int(dispatch_id)
                    if not order.dispatches.filter(pk=dispatch_id).exists():
                        dispatch_id = None
                except (ValueError, TypeError):
                    dispatch_id = None
            dispatched_lines = self._build_dispatch_lines(order, dispatch_id=dispatch_id, dispatch_date=dispatch_date)
        else:
            dispatched_lines = None
        from decimal import Decimal
        dispatch_total = sum((Decimal(str(d['total_price'])) for d in (dispatched_lines or [])), Decimal('0'))

        def gst_amount_from_line(total_price, gst_rate):
            """Given inclusive total and gst_rate %, return GST amount. total = base + base*rate/100 => base = total/(1+rate/100), gst = total - base."""
            total = Decimal(str(total_price))
            rate = Decimal(str(gst_rate or 0)) / Decimal('100')
            if rate <= 0:
                return Decimal('0')
            base = total / (1 + rate)
            return total - base

        if bill_type == 'dispatch' and dispatched_lines:
            gst_total = sum(
                gst_amount_from_line(d['total_price'], d.get('gst_rate'))
                for d in dispatched_lines
            )
        else:
            gst_total = Decimal('0')
            for item in order.items.filter(is_void=False):
                gst_total += gst_amount_from_line(item.total_price, item.gst_rate)

        template = get_template('invoices/invoice_template.html')
        context = {
            'invoice': invoice,
            'company': company,
            'bill_type': bill_type,
            'dispatched_lines': dispatched_lines,
            'dispatch_total': dispatch_total,
            'gst_total': gst_total,
        }
        html_content = template.render(context)

        pdf_file = HTML(string=html_content, base_url=request.build_absolute_uri()).write_pdf()
        suffix = '_dispatch' if bill_type == 'dispatch' else '_overall'
        if bill_type == 'dispatch' and dispatch_id:
            suffix = f'_dispatch_{dispatch_id}'
        elif bill_type == 'dispatch' and dispatch_date:
            suffix = f'_dispatch_{dispatch_date}'
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}{suffix}.pdf"'
        return response

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='company', permission_classes=[permissions.IsAuthenticated])
    def company_profile(self, request):
        """Get or update company profile (seller details for bills). Admin only for write."""
        company = CompanyProfile.objects.first()
        if request.method in ('PUT', 'PATCH'):
            if not (request.user and request.user.role == 'admin'):
                return Response({'detail': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
            if company is None:
                serializer = CompanyProfileSerializer(data=request.data)
            else:
                serializer = CompanyProfileSerializer(company, data=request.data, partial=(request.method == 'PATCH'))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        if company is None:
            return Response({})  # empty so frontend can show placeholder
        return Response(CompanyProfileSerializer(company).data)
