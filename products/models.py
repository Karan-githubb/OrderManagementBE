from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    description = models.TextField(blank=True, null=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    pack_size = models.PositiveIntegerField(default=1, help_text='Units per pack (e.g. 10 for strips of 10)')
    unit = models.CharField(max_length=50, blank=True, null=True, help_text='e.g. Strip, Box, Piece')
    default_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Discount percentage applied when ordering (0-100)')
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12) # Default 12%
    image_url = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class StockBatch(models.Model):
    """Batch-level inventory: (product, batch_number, expiry_date) = one lot. Same batch number with different expiry = separate lots."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    quantity = models.PositiveIntegerField(default=0)
    received_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [('product', 'batch_number', 'expiry_date')]
        ordering = ['expiry_date']

    def __str__(self):
        return f"{self.product.name} / {self.batch_number} (exp: {self.expiry_date})"


class Purchase(models.Model):
    STATUS_CHOICES = (('pending', 'Pending'), ('approved', 'Approved'))
    supplier_name = models.CharField(max_length=255)
    purchase_date = models.DateField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Purchase from {self.supplier_name} on {self.purchase_date}"

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    batch_number = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
