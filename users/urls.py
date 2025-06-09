from django.urls import path

from users.views import Login, RegisterUser, Logout,activate
app_name = "users"
urlpatterns = [
path("login/",Login.as_view(),name="login"),
path("register/",RegisterUser.as_view(),name="register"),
path("logout/", Logout.as_view(), name="logout"),
 path('activate/<uidb64>/<token>/', activate, name='activate'),
#  path('test-email/', test_email, name='test_email'),
]