from django.db import models

class Product(models.Model):

    CATEGORY_CHOICES = (
        ('Poultry', 'Poultry'),
        ('Cattle', 'Cattle'),
        ('Fish', 'Fish'),
    )

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
