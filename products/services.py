import os
from django.core.mail import send_mail
import africastalking

def send_order_sms(order):
    username = os.environ.get('AT_USERNAME')
    api_key = os.environ.get('AT_API_KEY')
    
    africastalking.initialize(username, api_key)
    sms = africastalking.SMS
    
    message = f"Your order #{order.id} has been received and is being processed."
    recipients = [order.customer.phone_number]
    
    try:
        response = sms.send(message, recipients)
        return response
    except Exception as e:
        print(f"Error sending SMS: {str(e)}")

def send_admin_email(order):
    subject = f'New Order #{order.id}'
    message = f"""
    Order Details:
    Customer: {order.customer.user.get_full_name()}
    Total Amount: ${order.total_amount}
    Items:
    {format_order_items(order)}
    """
    from_email = os.environ.get('EMAIL_FROM')
    admin_email = os.environ.get('ADMIN_EMAIL')
    
    send_mail(subject, message, from_email, [admin_email])
