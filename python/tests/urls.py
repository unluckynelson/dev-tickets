from django.urls import include, path

urlpatterns = [path("", include("dev_tickets.urls"))]
