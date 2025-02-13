from typing import Any, List
from django.db.models import Avg, QuerySet
from django.conf import settings
from django.core.mail import send_mail
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
import africastalking
from .models import Category, Customer, Product, Order, OrderItem
from .serializers import (
    CategorySerializer, CustomerSerializer, ProductSerializer,
    OrderSerializer, OrderItemSerializer
)

class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class for all ViewSets.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class BaseViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet with common functionality.
    """
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    def get_permissions(self):
        """
        Override to provide custom permission classes based on action.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = []
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

class CategoryViewSet(BaseViewSet):
    """
    ViewSet for managing product categories.
    
    list:
        Get all categories
    create:
        Create a new category (admin only)
    retrieve:
        Get a specific category
    update:
        Update a category (admin only)
    delete:
        Delete a category (admin only)
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self) -> QuerySet:
        """
        Optionally restricts the returned categories to active ones.
        """
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset

class ProductViewSet(BaseViewSet):
    """
    ViewSet for managing products.
    
    Supports filtering by category and searching by name/description.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at']

    def get_queryset(self) -> QuerySet:
        """
        Optionally filters products by category and active status.
        """
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)

        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
            
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def update_stock(self, request: Any, pk: None = None) -> Response:
        """
        Update product stock levels.
        """
        product = self.get_object()
        new_stock = request.data.get('stock')
        
        if new_stock is None:
            return Response(
                {'error': 'Stock value required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_stock = int(new_stock)
            if new_stock < 0:
                raise ValueError
        except ValueError:
            return Response(
                {'error': 'Invalid stock value'},
                status=status.HTTP_400_BAD_REQUEST
            )

        product.stock = new_stock
        product.save()
        return Response({'status': 'Stock updated successfully'})

    @action(detail=False, methods=['get'])
    def category_average(self, request: Any) -> Response:
        """
        Get average product price by category.
        """
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'Category ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        avg_price = Product.objects.filter(
            categories__id=category_id,
            is_active=True
        ).aggregate(average_price=Avg('price'))

        return Response(avg_price)

class CustomerViewSet(BaseViewSet):
    """
    ViewSet for managing customer profiles.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['user__username', 'phone_number']
    ordering_fields = ['created_at']

    def get_queryset(self) -> QuerySet:
        """
        Restrict customers to viewing only their own profile unless admin.
        """
        if self.request.user.is_staff:
            return Customer.objects.all()
        return Customer.objects.filter(user=self.request.user)

class OrderViewSet(BaseViewSet):
    """
    ViewSet for managing orders.
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ['created_at', 'status']

    def get_queryset(self) -> QuerySet:
        """
        Restrict orders to customer's own unless admin.
        """
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(customer__user=self.request.user)

    def perform_create(self, serializer: OrderSerializer) -> None:
        """
        Create order and send notifications.
        """
        order = serializer.save()
        self._send_order_notifications(order)

    def _send_order_notifications(self, order: Order) -> None:
        """
        Send SMS to customer and email to admin.
        """
        # Send SMS
        try:
            africastalking.initialize(
                settings.AT_USERNAME,
                settings.AT_API_KEY
            )
            sms = africastalking.SMS
            message = f"Your order #{order.id} has been received and is being processed."
            sms.send(message, [order.customer.phone_number])
        except Exception as e:
            print(f"SMS sending failed: {str(e)}")

        # Send Email
        try:
            send_mail(
                subject=f'New Order #{order.id}',
                message=self._format_order_email(order),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email sending failed: {str(e)}")

    def _format_order_email(self, order: Order) -> str:
        """
        Format order details for email notification.
        """
        items = OrderItem.objects.filter(order=order)
        items_text = "\n".join(
            f"- {item.quantity}x {item.product.name} @ ${item.price_at_time}"
            for item in items
        )
        
        return f"""
        New Order Received
        
        Order ID: {order.id}
        Customer: {order.customer.user.get_full_name() or order.customer.user.username}
        Phone: {order.customer.phone_number}
        
        Items:
        {items_text}
        
        Total Amount: ${order.total_amount}
        """
