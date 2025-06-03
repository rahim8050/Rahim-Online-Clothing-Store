from django.urls import path
from utilities import about, contact, terms, privacy
app_name = 'utilities'
urlpatterns = [
    path('about/', about, name='about'),
    path('contact/', contact, name='contact'),
    path('terms/', terms, name='terms'),
    path('privacy/',privacy, name='privacy'),
]