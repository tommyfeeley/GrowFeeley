from django.urls import path
from . import views

app_name = 'garden'

urlpatterns = [
    path('', views.home, name='home'),
    path('plants/', views.plant_list, name='plant_list'),
    path('plants/<int:pk>/', views.plant_detail, name='plant_detail'),
    path('my-garden/', views.my_garden, name='my_garden'),
    path('chat/', views.garden_chat, name='chat'),

    # API endpoints
    path('api/zone-lookup/', views.api_lookup_zone, name='api_zone_lookup'),
    path('api/plant-search/', views.api_plant_search, name='api_plant_search'),
    path('api/chat/', views.api_chat, name='api_chat'),
]
