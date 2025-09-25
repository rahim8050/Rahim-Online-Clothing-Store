from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from users.views import (
    CustomLoginView,
    Logout,
    RegisterUser,
    VendorApplicationApproveAPI,
    activate,
    after_login,
    change_password_view,
    driver_dashboard,
    driver_live,
    driver_sim,
    geoapify_test,
    my_orders,
    profile_settings_view,
    profile_view,
    vendor_apply_deprecated,
    vendor_dashboard,
)

from .views import ResendActivationEmailView

app_name = "users"

urlpatterns = [
    # Auth basics
    path("login/", CustomLoginView.as_view(), name="login"),
    path("register/", RegisterUser.as_view(), name="register"),
    path("logout/", Logout.as_view(), name="logout"),
    path("activate/<uidb64>/<token>/", activate, name="activate"),
    path(
        "resend-activation/",
        ResendActivationEmailView.as_view(),
        name="resend_activation",
    ),
    # Profile / account
    path("profile/", profile_view, name="profile"),
    path("profile/settings/", profile_settings_view, name="profile_settings"),
    path("profile/password/", change_password_view, name="change_password"),
    path("my-orders/", my_orders, name="my_orders"),
    path("after-login/", after_login, name="after_login"),
    # Dashboards
    path("vendor-dashboard/", vendor_dashboard, name="vendor_dashboard"),
    path("driver-dashboard/", driver_dashboard, name="driver_dashboard"),
    # Vendor applications (legacy + admin action)
    # Deprecated: kept for compatibility (new flow under /apis/vendor/apply/)
    path("vendor-applications/", vendor_apply_deprecated, name="vendor-apply"),
    path(
        "vendor-applications/<int:pk>/approve/",
        VendorApplicationApproveAPI.as_view(),
        name="vendor-application-approve",
    ),
    # Driver tools / live tracking
    path("driver/sim/", driver_sim, name="driver-sim"),
    path("driver/live/<int:delivery_id>/", driver_live, name="driver-live"),
    # Dev utilities
    path("dev/geoapify/", geoapify_test, name="geoapify-test"),
    # Password reset flow
    path(
        "reset_password/",
        auth_views.PasswordResetView.as_view(
            template_name="users/accounts/password_reset.html",
            success_url=reverse_lazy("users:password_reset_done"),
            email_template_name="users/accounts/password_reset_email.html",
            subject_template_name="users/accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "reset_password_sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="users/accounts/password_reset_sent.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="users/accounts/password_reset_confirm.html",
            success_url=reverse_lazy("users:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset_password_complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="users/accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
