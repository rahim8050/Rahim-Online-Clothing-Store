from django.urls import path
from .views import ResendActivationEmailView
from django.contrib.auth import views as auth_views
from users.views import Login,Logout,RegisterUser,activate, profile_view,my_orders
from django.urls import reverse_lazy

app_name = "users"
urlpatterns = [
path("login/",Login.as_view(),name="login"),
path("register/",RegisterUser.as_view(),name="register"),
path("logout/", Logout.as_view(), name="logout"),
path('activate/<uidb64>/<token>/', activate, name='activate'),
path('profile/', profile_view, name='profile'),
path('resend-activation/', ResendActivationEmailView.as_view(), name='resend_activation'),
path('my-orders/', my_orders, name='my_orders'),
# password reset flow


#  path('test-email/', test_email, name='test_email'),
]