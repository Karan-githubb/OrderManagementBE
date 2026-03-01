from django.db import models
from django.db.models import Sum, F
from decimal import Decimal
from pharmacies.models import Pharmacy
from products.models import Product, StockBatch
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
    
    # Track if stock has been deducted to prevent duplicate deductions
    stock_deducted = models.BooleanField(default=False)
    is_void = models.BooleanField(default=False, help_text='Voided orders are excluded from active totals and reports.')
    
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

    def dispatched_amount(self):
        """Total value of items actually dispatched (for payment collection). Excludes voided items."""
        result = OrderItemAllocation.objects.filter(
            order_item__order=self, order_item__is_void=False
        ).aggregate(total=Sum(F('quantity') * F('order_item__unit_price')))
        return result['total'] or Decimal('0')

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    free_qty = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_void = models.BooleanField(default=False, help_text='Voided line items are excluded from order totals.')

    def __str__(self):
        return f"{self.product.name} ({self.order.order_number})"

    @property
    def dispatched_quantity(self):
        return self.allocations.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def remaining_quantity(self):
        return self.quantity - self.dispatched_quantity


class Dispatch(models.Model):
    """
    One record per dispatch event (e.g. one "Save dispatch" from the dispatch screen).
    Groups multiple OrderItemAllocations so each event can have its own bill.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='dispatches')
    dispatched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dispatch #{self.id} — {self.order.order_number}"

    def total_value(self):
        result = OrderItemAllocation.objects.filter(
            dispatch=self
        ).aggregate(total=Sum(F('quantity') * F('order_item__unit_price')))
        return result['total'] or Decimal('0')


class OrderItemAllocation(models.Model):
    """Which batch and how much was dispatched for an order line. Enables partial dispatch."""
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='allocations')
    stock_batch = models.ForeignKey(StockBatch, on_delete=models.CASCADE, related_name='order_allocations')
    quantity = models.PositiveIntegerField()
    dispatch = models.ForeignKey(Dispatch, on_delete=models.CASCADE, null=True, blank=True, related_name='allocations')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order_item.product.name} batch {self.stock_batch.batch_number} x {self.quantity}"
