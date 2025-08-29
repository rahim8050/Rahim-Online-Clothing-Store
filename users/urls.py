from django.urls import path
from .views import ResendActivationEmailView
from django.contrib.auth import views as auth_views
from users.views import (
    CustomLoginView,
    Logout,
    RegisterUser,
    activate,
    profile_view,
    profile_settings_view,
    change_password_view,
    my_orders,
    geoapify_test,
    vendor_dashboard,
    driver_dashboard,
    after_login,
    VendorApplyAPI,
    VendorApplicationApproveAPI,
    driver_sim,
    driver_live,
    after_login,
)
from django.urls import reverse_lazy


app_name = "users"
urlpatterns = [
path("login/",CustomLoginView.as_view(),name="login"),
path("register/",RegisterUser.as_view(),name="register"),
path("logout/", Logout.as_view(), name="logout"),
path('activate/<uidb64>/<token>/', activate, name='activate'),
path('profile/', profile_view, name='profile'),
path('profile/settings/', profile_settings_view, name='profile_settings'),
path('profile/password/', change_password_view, name='change_password'),
path('resend-activation/', ResendActivationEmailView.as_view(), name='resend_activation'),
path('my-orders/', my_orders, name='my_orders'),
path('vendor-dashboard/', vendor_dashboard, name='vendor_dashboard'),
    path('driver-dashboard/', driver_dashboard, name='driver_dashboard'),
    path('after-login/', after_login, name='after_login'),
    path('vendor-applications/', VendorApplyAPI.as_view(), name='vendor-apply'),
    path('vendor-applications/<int:pk>/approve/', VendorApplicationApproveAPI.as_view(), name='vendor-application-approve'),
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


     path("after-login/", after_login, name="after_login"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/accounts/password_reset_complete.html'
    ), name='password_reset_complete'),

     path("dev/geoapify/", geoapify_test, name="geoapify-test"),
     path("driver/sim/", driver_sim, name="driver-sim"),
     path("driver/live/<int:delivery_id>/", driver_live, name="driver-live"),

]
