from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from routing.route.routing import optimize_route
from routing.route.visualize_route import create_route_map


@require_http_methods(["GET", "POST"])
def route_form(request):
    if request.method == "POST":
        origin = request.POST.get("origin")
        destination = request.POST.get("destination")

        if not origin or not destination:
            return render(
                request,
                "route/form.html",
                {"error": "Both origin and destination are required."},
            )

        origin = origin.strip().lower()
        destination = destination.strip().lower()
        route_result = optimize_route(origin, destination)
        map_obj = create_route_map(route_result, origin, destination)

        return render(
            request,
            "route/form.html",
            {
                "origin": origin,
                "destination": destination,
                "map_html": map_obj._repr_html_(),
                "route_result": route_result,
            },
        )

    return render(request, "route/form.html")
