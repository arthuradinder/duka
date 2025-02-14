from typing import Any, List
import logging
from django.db.models import Avg, QuerySet
from django.conf import settings
from django.core.mail import send_mail
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
import africastalking
from drf_spectacular.utils import extend_schema
from .models import Category, Customer, Product, Order, OrderItem
from .serializers import (
    CategorySerializer, CustomerSerializer, ProductSerializer,
    OrderSerializer, OrderItemSerializer, StockUpdateSerializer
)
from .services import send_order_sms, send_admin_email

# Configure logging
logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class BaseViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return []
        return [IsAdminUser()]

class CategoryViewSet(BaseViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset

class ProductViewSet(BaseViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at']

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    @extend_schema(request=StockUpdateSerializer, responses={200: "Stock updated successfully"})
    def update_stock(self, request: Any, pk: None = None) -> Response:
        product = self.get_object()
        serializer = StockUpdateSerializer(data=request.data)
        if serializer.is_valid():
            product.stock = serializer.validated_data['stock']
            product.save()
            return Response({'status': 'Stock updated successfully'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def category_average(self, request: Any) -> Response:
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response({'error': 'Category ID required'}, status=status.HTTP_400_BAD_REQUEST)
        avg_price = Product.objects.filter(category_id=category_id, is_active=True).aggregate(average_price=Avg('price'))
        return Response(avg_price)

class CustomerViewSet(BaseViewSet):
    queryset = Customer.objects.select_related('user').all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['user__username', 'phone_number']
    ordering_fields = ['created_at']

    def get_queryset(self) -> QuerySet:
        if self.request.user.is_staff:
            return Customer.objects.all()
        return Customer.objects.filter(user=self.request.user)

class OrderViewSet(BaseViewSet):
    queryset = Order.objects.prefetch_related('order_items').all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ['created_at', 'status']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self) -> QuerySet:
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(customer__user=self.request.user)

    def perform_create(self, serializer: OrderSerializer) -> None:
        order = serializer.save()
        self._send_order_notifications(order)

    def _send_order_notifications(self, order: Order) -> None:
        """Calls services.py functions to send notifications"""
        send_order_sms(order)
        send_admin_email(order)
        logger.info(f"Order {order.id} processed successfully")
        
    def _format_order_email(self, order: Order) -> str:
        items = OrderItem.objects.filter(order=order)
        items_text = "\n".join(
            f"- {item.quantity}x {item.product.name} @ ${item.price_at_time}" for item in items
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
