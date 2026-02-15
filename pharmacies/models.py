from django.db import models

class Pharmacy(models.Model):
    pharmacy_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100, unique=True)
    gst_number = models.CharField(max_length=15, unique=True)
    contact_person = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    address = models.TextField()
    is_active = models.BooleanField(default=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.pharmacy_name

    class Meta:
        verbose_name_plural = "Pharmacies"
