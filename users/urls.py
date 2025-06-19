from django.urls import path
from .views import ResendActivationEmailView
from django.contrib.auth import views as auth_views
from users.views import Login,Logout,RegisterUser,activate, profile_view
from django.urls import reverse_lazy
app_name = "users"
urlpatterns = [
path("login/",Login.as_view(),name="login"),
path("register/",RegisterUser.as_view(),name="register"),
path("logout/", Logout.as_view(), name="logout"),
 path('activate/<uidb64>/<token>/', activate, name='activate'),
 path('profile/', profile_view, name='profile'),
  path('resend-activation/', ResendActivationEmailView.as_view(), name='resend_activation'),
      # Password reset flow
path(
    'password_reset/',
    auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        success_url=reverse_lazy('users:password_reset_done')
    ),
    name='password_reset'
),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),
#  path('test-email/', test_email, name='test_email'),
]