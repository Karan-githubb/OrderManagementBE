from django.db import models
from pharmacies.models import Pharmacy
from products.models import Product
import datetime

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
    )
    PAYMENT_CHOICES = (
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    )
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=30, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='unpaid')
    
    # New fields for professional invoice
    salesman_name = models.CharField(max_length=100, blank=True, null=True)
    terms = models.CharField(max_length=100, default='D-CREDIT BILL')
    delivery_type = models.CharField(max_length=100, default='DIRECT')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            prefix = 'ORD-' + datetime.datetime.now().strftime('%Y%m%d')
            last_order = Order.objects.filter(order_number__startswith=prefix).order_by('id').last()
            if not last_order:
                self.order_number = prefix + '-0001'
            else:
                last_number = int(last_order.order_number.split('-')[-1])
                self.order_number = prefix + '-' + str(last_number + 1).zfill(4)
        super(Order, self).save(*args, **kwargs)

    def __str__(self):
        return self.order_number

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    free_qty = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} ({self.order.order_number})"
