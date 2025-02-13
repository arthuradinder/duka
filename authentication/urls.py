from django.urls import path

from .views import signup, login, test_token

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('login/', login, name='login'),
    path('test-token/', test_token, name='test-token'),
]