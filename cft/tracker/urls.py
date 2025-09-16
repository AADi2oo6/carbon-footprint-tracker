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
    path('activity/', views.activity, name='activity'),

    path('community/', views.community_view, name='community'),
    path('community/<int:pk>/', views.community_detail_view, name='community-detail'),
    path('community/<int:pk>/join/', views.join_community, name='join-community'),
    path('community/<int:pk>/leave/', views.leave_community, name='leave-community'),
    path('challenges/', views.challenges_view, name='challenges'),
    path('challenge/<int:pk>/join/', views.join_challenge, name='join-challenge'),

]
