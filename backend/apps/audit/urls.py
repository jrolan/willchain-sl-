from django.urls import path

from .views import MyActivityListAPIView

app_name = 'audit'

urlpatterns = [
    path('me/activity/', MyActivityListAPIView.as_view(), name='my-activity'),
]
