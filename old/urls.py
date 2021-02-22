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
from django.contrib import admin
from django.urls import path, include, re_path

from timecardsite import views as tc_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', tc_views.index, name='landing'),
    path('account/', include('allauth.urls')),
    re_path(r'^auth/?code=(?P<code>\w{1,64})', tc_views.auth, name='authorization'),
    path('post_login/', tc_views.post_login, name='post_login'),
    path('connect/', tc_views.connect, name='connect'),
    path('onboard', tc_views.onboard, name='onboard'),
    path('manager/', tc_views.manager, name='manager'),
    path('employee/', tc_views.employee, name='employee'),
    path('invite/', tc_views.invite, name='invite'),
    path('invitations/', include('invitations.urls', namespace='invitations')),
    re_path(r'^test/?code=(?P<code>\w{1,64})/$', tc_views.test, name='test')
]
