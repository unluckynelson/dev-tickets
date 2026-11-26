from django.urls import include, path

from . import views

urlpatterns = [
    path("playground/", views.people),
    path("playground/login/<str:username>/", views.login_as),
    path("playground/logout/", views.logout_view),
    path("", include("dev_tickets.urls")),
]
