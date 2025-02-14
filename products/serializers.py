from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Customer, Category, Product, Order, OrderItem
from decimal import Decimal
from typing import Dict, Any, List

class TimestampedSerializer(serializers.ModelSerializer):
    """
    Base serializer for models with timestamp fields.
    Provides common timestamp field handling.
    """
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

class StockUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating product stock.
    """
    class Meta:
        model = Product
        fields = ['id','stock']

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with additional validation.
    """
    email = serializers.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']
        
    def validate_email(self, value: str) -> str:
        """
        Validate email uniqueness.
        """
        if self.instance and self.instance.email == value:
         return value  # Allow unchanged email
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

class CustomerSerializer(TimestampedSerializer):
    """
    Customer serializer with nested user details and order summary.
    """
    user = UserSerializer()
    total_orders = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = ['id', 'user', 'phone_number', 'address', 
                 'created_at', 'updated_at', 'total_orders', 'is_active']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_orders(self, obj: Customer) -> int:
        """
        Get total number of orders for the customer.
        """
        return obj.orders.count()

    def create(self, validated_data: Dict[str, Any]) -> Customer:
        """
        Create customer with nested user data.
        """
        user_data = validated_data.pop('user')
        user = User.objects.create_user(**user_data)
        customer = Customer.objects.create(user=user, **validated_data)
        return customer

class CategorySerializer(TimestampedSerializer):
    """
    Recursive serializer for hierarchical category structure.
    """
    subcategories = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'parent', 'subcategories', 
                 'products_count', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_subcategories(self, obj: Category) -> List[Dict[str, Any]]:
        """
        Recursively serialize child categories.
        """
        return CategorySerializer(obj.children.filter(is_active=True), 
                                many=True).data

    def get_products_count(self, obj: Category) -> int:
        """
        Get total number of products in category and subcategories.
        """
        return obj.get_products_count()

class ProductSerializer(TimestampedSerializer):
    """
    Product serializer with category details and stock information.
    """
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        many=True,
        write_only=True,
        source='categories'
    )
    in_stock = serializers.BooleanField(source='is_in_stock', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'categories', 
                 'category_ids', 'stock', 'in_stock', 'is_active', 
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_price(self, value: Decimal) -> Decimal:
        """
        Validate price is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

class OrderItemSerializer(TimestampedSerializer):
    """
    Serializer for order items with product details and subtotal calculation.
    """
    product = serializers.StringRelatedField(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        write_only=True,
        source='product'
    )
    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        source='get_subtotal'
    )

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_id', 'quantity', 'price_at_time',
                 'subtotal', 'created_at', 'updated_at']
        read_only_fields = ['id', 'price_at_time', 'created_at', 'updated_at']

    def validate_quantity(self, value: int) -> int:
        """
        Validate quantity is positive.
        """
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate product stock availability.
        """
        product = data['product']
        quantity = data['quantity']
        
        if quantity > product.stock:
            raise serializers.ValidationError(
                f"Only {product.stock} items available in stock."
            )
        return data

class OrderSerializer(TimestampedSerializer):
    """
    Order serializer with nested customer and order items.
    """
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.filter(is_active=True),
        write_only=True,
        source='customer'
    )
    order_items = OrderItemSerializer(many=True, read_only=True)
    items_data = OrderItemSerializer(many=True, write_only=True, source='order_items')
    total_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Order
        fields = ['id', 'customer', 'customer_id', 'order_items', 'items_data',
                 'status', 'total_amount', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at']

    def create(self, validated_data: Dict[str, Any]) -> Order:
        """
        Create order with nested order items.
        """
        items_data = validated_data.pop('order_items')
        # Check stock availability before creating order
        for item in items_data:
            product, quantity = item['product'], item['quantity']
            if product.stock < quantity:
                raise serializers.ValidationError(
                    f"Insufficient stock for {product.name} ({product.stock} available)."
                )

        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            product = item_data['product']
            product.stock -= item_data['quantity']
            product.save()
            OrderItem.objects.create(order=order, **item_data)

        order.calculate_total()
        return order

    def validate_items_data(self, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate that order contains at least one item.
        """
        if not value:
            raise serializers.ValidationError(
                "Order must contain at least one item."
            )
        return value
