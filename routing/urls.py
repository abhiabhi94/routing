from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include
from django.urls import path

urlpatterns = [
    path("", lambda request: redirect("route/")),
    path("admin/", admin.site.urls),
    path("route/", include("routing.route.urls")),
]
