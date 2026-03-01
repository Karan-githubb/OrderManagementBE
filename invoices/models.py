from django.db import models
from orders.models import Order
import datetime


class CompanyProfile(models.Model):
    """Single-row table storing seller/distributor details for bills and reports."""
    company_name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    gst_number = models.CharField(max_length=30, blank=True)
    license_number = models.CharField(max_length=100, blank=True, help_text='Drug license / DL number')
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Company profile'

    def __str__(self):
        return self.company_name or 'Company'


class Invoice(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='invoice')
    invoice_number = models.CharField(max_length=30, unique=True, editable=False)
    pdf_file = models.FileField(upload_to='invoices/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = datetime.datetime.now().strftime('%Y')
            prefix = f'INV-{year}'
            last_invoice = Invoice.objects.filter(invoice_number__startswith=prefix).order_by('id').last()
            if not last_invoice:
                self.invoice_number = f'{prefix}-0001'
            else:
                try:
                    last_number = int(last_invoice.invoice_number.split('-')[-1])
                    self.invoice_number = f'{prefix}-{str(last_number + 1).zfill(4)}'
                except (ValueError, IndexError):
                    self.invoice_number = f'{prefix}-0001'
        super(Invoice, self).save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number
