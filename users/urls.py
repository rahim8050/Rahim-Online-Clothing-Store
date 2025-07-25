from django.urls import path
from .views import ResendActivationEmailView
from django.contrib.auth import views as auth_views
from users.views import CustomLoginView,Logout,RegisterUser,activate, profile_view,my_orders
from django.urls import reverse_lazy


app_name = "users"
urlpatterns = [
path("login/",CustomLoginView.as_view(),name="login"),
path("register/",RegisterUser.as_view(),name="register"),
path("logout/", Logout.as_view(), name="logout"),
path('activate/<uidb64>/<token>/', activate, name='activate'),
path('profile/', profile_view, name='profile'),
path('resend-activation/', ResendActivationEmailView.as_view(), name='resend_activation'),
path('my-orders/', my_orders, name='my_orders'),
# Password reset URLs
    # These URLs are used for password reset functionality
    path('reset_password/', auth_views.PasswordResetView.as_view(
        template_name='users/accounts/password_reset.html',
        success_url=reverse_lazy('users:password_reset_done'),
        email_template_name='users/accounts/password_reset_email.html',  
        subject_template_name='users/accounts/password_reset_subject.txt',  
    ), name='password_reset'),

    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/accounts/password_reset_sent.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/accounts/password_reset_confirm.html',
        success_url=reverse_lazy('users:password_reset_complete')
    ), name='password_reset_confirm'),

    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/accounts/password_reset_complete.html'
    ), name='password_reset_complete'),

     

]