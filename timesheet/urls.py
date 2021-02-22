"""timesheet URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from timecardsite import views

urlpatterns = [
    path('', views.index, name='index'),

    path('auth/', views.auth, name='auth'),
    path('post_login/', views.post_login, name='post_login'),
    path('onboard/', views.onboard, name='onboard'),

    path('timecard/', views.timecard, name='timecard'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('account/', include('allauth.urls')),
]
