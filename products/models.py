import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from django.core.exceptions import ValidationError
from mptt.models import MPTTModel, TreeForeignKey

class TimestampedModel(models.Model):
    """Abstract base class with timestamp fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Category(MPTTModel, TimestampedModel):
    """Hierarchical category model for products."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    parent = TreeForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
        help_text="Parent category if this is a sub-category."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ['name']

    class MPTTMeta:
        order_insertion_by = ["name"]

    def __str__(self):
        return f"{self.parent.name} -> {self.name}" if self.parent else self.name

    def get_products_count(self):
        """Returns total number of products in this category and its subcategories."""
        return Product.objects.filter(categories__in=self.get_descendants(include_self=True)).count()

class Customer(TimestampedModel):
    """Customer model extending the User model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer"
    )
    phone_number = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    def get_total_orders(self):
        """Returns total number of orders made by customer."""
        return self.orders.count()

class Product(TimestampedModel):
    """Product model with category relationship."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    categories = models.ManyToManyField(
        Category,
        related_name="products",
        help_text="Categories this product belongs to"
    )
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate the product data."""
        if self.price <= 0:
            raise ValidationError('Price must be greater than zero')
        if self.stock < 0:
            raise ValidationError('Stock cannot be negative')

    def save(self, *args, **kwargs):
        if not self.pk:  # Only reduce stock on first save
            if self.product.stock < self.quantity:
             raise ValidationError(f"Not enough stock for {self.product.name}")
            self.product.stock -= self.quantity
            self.product.save()
        super().save(*args, **kwargs)
        self.order.calculate_total()

    def is_in_stock(self):
        """Check if product is in stock."""
        return self.stock > 0

class Order(TimestampedModel):
    """Order model to track customer purchases."""
    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="orders"
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} by {self.customer}"

    def calculate_total(self):
        """Calculate total amount for the order and save it."""
        total = sum(
            item.get_subtotal() for item in self.order_items.all()
        )
        if self.total_amount != total:
            self.total_amount = total
            self.save()

class OrderItem(TimestampedModel):
    """Individual items within an order."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="order_items"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="order_items"
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    price_at_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price of the product at the time of order"
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order {self.order.id}"

    def save(self, *args, **kwargs):
        self.price_at_time = self.product.price  # Always store price history
        super().save(*args, **kwargs)
        # Update order total
        self.order.calculate_total()

    def get_subtotal(self):
        """Calculate subtotal for this order item."""
        return self.quantity * self.price_at_time
