# tracker/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # URL for the home page
    path('', views.home, name='tracker-home'),
    # URL for the registration page, using the view we created
    path('register/', views.register, name='register'),
    # URL for the login page, using Django's built-in LoginView
    # We specify the template to use
    path('login/', auth_views.LoginView.as_view(template_name='tracker/login.html'), name='login'),
    # URL for the logout page, using Django's built-in LogoutView
    # We specify the template to use
    path('logout/', auth_views.LogoutView.as_view(template_name='tracker/logout.html'), name='logout'),

    path('myprofile/', views.myprofile, name='myprofile'),
    path('logactivity/', views.logactivity),

]
