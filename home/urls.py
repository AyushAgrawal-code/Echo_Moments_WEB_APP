# from django.contrib import admin
from django.urls import path, include
from home import views
urlpatterns = [
    path('', views.index, name ='index'),
    # path('album/', views.album, name ='album'),
    # # path('login/', views.login, name ='login'),
    # path('dashboard/', views.dashboard, name='dashboard'),
    # path('host_dashboard/', views.host_dashboard, name='host_dashboard'),
    # path('guest_dashboard/', views.guest_dashboard, name='guest_dashboard'),
    # path('centralised_album/', views.centralised_album , name='centralised_album'),
    # path('logout/', views.logout_view, name='logout'),
    # path('host/', views.host, name='host')


]
