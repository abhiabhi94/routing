from django.urls import path

from . import views

app_name = "route"

urlpatterns = [
    path("", views.route_form, name="form"),
]
