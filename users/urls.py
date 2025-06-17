from django.urls import path
from .views import ResendActivationEmailView
from users.views import Login,Logout,RegisterUser,activate, profile_view 
app_name = "users"
urlpatterns = [
path("login/",Login.as_view(),name="login"),
path("register/",RegisterUser.as_view(),name="register"),
path("logout/", Logout.as_view(), name="logout"),
 path('activate/<uidb64>/<token>/', activate, name='activate'),
 path('profile/', profile_view, name='profile'),
  path('resend-activation/', ResendActivationEmailView.as_view(), name='resend_activation'),
#  path('test-email/', test_email, name='test_email'),
]