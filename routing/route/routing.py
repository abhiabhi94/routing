import json
import pathlib
from dataclasses import dataclass
from typing import List
from typing import Optional

import httpx
import polyline
from geopy.distance import geodesic

from routing import settings


ROUTE_SERVICE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
GEOCODE_SERVICE_URL = "https://nominatim.openstreetmap.org/search"
GAS_STATIONS = "data/gas_stations.json"
# 10 miles per gallon
GAS_EFFICIENCY = 10
# all in miles
VEHICLE_RANGE = 500
WAYPOINT_INTERVAL = 450
GAS_SEARCH_RADIUS = 20
DETOUR_ALLOWANCE = 10.0  # Total detour distance to/from gas stations (miles)
HIGHWAY_BONUS = 0.05  # 5 cents per gallon discount for highway accessible stops


@dataclass
class Coordinates:
    latitude: float
    longitude: float

    def to_tuple(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)


@dataclass
class GasStop:
    truckstop_id: str
    name: str
    address: str
    city: str
    state: str
    coordinates: Coordinates
    price_per_gallon: float


@dataclass
class Route:
    origin_coordinates: Coordinates
    destination_coordinates: Coordinates
    distance: float
    geometry: list[Coordinates]
    bbox: List[float]  # [min_lon, min_lat, max_lon, max_lat]


@dataclass
class RouteSegment:
    start_coordinates: Coordinates
    end_coordinates: Coordinates
    distance: float
    gas_needed_gallons: float


@dataclass
class OptimalRoute:
    total_distance: float
    total_gas_cost: float
    gas_stops: list[GasStop]
    route_coordinates: list[Coordinates]
    segments: list[RouteSegment]
    nearby_stations: list[list[GasStop]]


def optimize_route(origin_city: str, destination_city: str) -> OptimalRoute:
    route = get_route(origin_city, destination_city)

    waypoints = calculate_waypoints(route)
    optimal_gas_stops, nearby_stations = find_optimal_gas_stops(waypoints, route)
    segments = calculate_route_segments(route, optimal_gas_stops)
    total_cost = calculate_total_gas_cost(segments, optimal_gas_stops)

    return OptimalRoute(
        total_distance=route.distance,
        total_gas_cost=total_cost,
        gas_stops=optimal_gas_stops,
        route_coordinates=route.geometry,
        segments=segments,
        nearby_stations=nearby_stations,
    )


def get_route(origin_city: str, destination_city: str) -> Route:
    """https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/json/post"""
    origin_coords = geocode_address(f"{origin_city}, USA")
    destination_coords = geocode_address(f"{destination_city}, USA")

    payload = {
        "coordinates": [
            [origin_coords.longitude, origin_coords.latitude],
            [destination_coords.longitude, destination_coords.latitude],
        ],
        # "alternative_routes": {"target_count": 3},
        "instructions": "false",
        "geometry": "true",
        "units": "mi",  # miles
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": settings.ROUTE_SERVICE_API_KEY,
    }

    response = httpx.post(ROUTE_SERVICE_URL, json=payload, headers=headers)
    response.raise_for_status()
    route_data = response.json()
    route = route_data["routes"][0]
    summary = route["summary"]
    geometry = [
        Coordinates(latitude=lat, longitude=lon)
        for lat, lon in polyline.decode(route["geometry"])
    ]
    return Route(
        origin_coordinates=origin_coords,
        destination_coordinates=destination_coords,
        distance=summary["distance"],
        geometry=geometry,
        bbox=route["bbox"],
    )


def geocode_address(address: str) -> Optional[Coordinates]:
    """https://nominatim.org/release-docs/develop/api/Search/#endpoint"""
    params = {"q": address, "format": "json", "limit": 1, "countrycodes": "us"}

    response = httpx.get(GEOCODE_SERVICE_URL, params=params)
    response.raise_for_status()

    data = response.json()

    return Coordinates(latitude=float(data[0]["lat"]), longitude=float(data[0]["lon"]))


def calculate_waypoints(route: Route) -> list[Coordinates]:
    total_distance = route.distance

    if total_distance <= VEHICLE_RANGE:
        return []

    cumulative_distances = calculate_cumulative_distances(route.geometry)
    waypoints = []
    target_distance = WAYPOINT_INTERVAL

    while target_distance < total_distance:
        waypoint_coords = find_point_at_distance(
            route_points=route.geometry,
            cumulative_distances=cumulative_distances,
            target_distance=target_distance,
        )
        if waypoint_coords:
            waypoints.append(waypoint_coords)

        target_distance += WAYPOINT_INTERVAL

    return waypoints


def calculate_cumulative_distances(route_points: List[Coordinates]) -> List[float]:
    distances = [0.0]
    for point_index in range(1, len(route_points)):
        segment_distance = geodesic(
            route_points[point_index - 1].to_tuple(),
            route_points[point_index].to_tuple(),
        ).miles
        distances.append(distances[-1] + segment_distance)
    return distances


def find_point_at_distance(
    route_points: List[Coordinates],
    cumulative_distances: List[float],
    target_distance: float,
) -> Optional[Coordinates]:
    for distance_index in range(len(cumulative_distances) - 1):
        if (
            cumulative_distances[distance_index]
            <= target_distance
            <= cumulative_distances[distance_index + 1]
        ):
            return route_points[distance_index]
    return None


def find_optimal_gas_stops(
    waypoints: list[Coordinates], route: Route
) -> tuple[list[GasStop], list[list[GasStop]]]:
    optimal_stops = []
    all_nearby_stations = []

    # Filter gas stations using bounding box once
    filtered_gas_stops = get_nearby_gas_stops(route)

    for waypoint in waypoints:
        nearby_stops = []
        for gas_stop in filtered_gas_stops:
            distance = geodesic(
                waypoint.to_tuple(), gas_stop.coordinates.to_tuple()
            ).miles
            if distance <= GAS_SEARCH_RADIUS:
                nearby_stops.append(gas_stop)

        all_nearby_stations.append(nearby_stops)

        best_stop = select_cheapest_gas_stop(nearby_stops)
        if best_stop:
            optimal_stops.append(best_stop)

    return optimal_stops, all_nearby_stations


def get_nearby_gas_stops(route: Route) -> list[GasStop]:
    """Filter gas stations by route bounding box"""
    min_lon, min_lat, max_lon, max_lat = route.bbox
    gas_stops = get_gas_stops()

    filtered_stops = []
    for gas_stop in gas_stops:
        lat = gas_stop.coordinates.latitude
        lon = gas_stop.coordinates.longitude

        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            filtered_stops.append(gas_stop)

    return filtered_stops


GAS_STOPS: Optional[list[GasStop]] = []


def get_gas_stops() -> list[GasStop]:
    global GAS_STOPS
    if GAS_STOPS:
        return GAS_STOPS

    with open(pathlib.Path(settings.BASE_DIR / GAS_STATIONS), "r") as f:
        gas_data = json.load(f)

    gas_stops = []
    for data in gas_data:
        gas_stop = GasStop(
            truckstop_id=data["truckstop_id"],
            name=data["name"],
            address=data["address"],
            city=data["city"],
            state=data["state"],
            coordinates=Coordinates(
                latitude=data["latitude"], longitude=data["longitude"]
            ),
            price_per_gallon=data["price_per_gallon"],
        )
        gas_stops.append(gas_stop)

    GAS_STOPS = gas_stops
    return GAS_STOPS


def select_cheapest_gas_stop(candidate_stops: list[GasStop]) -> Optional[GasStop]:
    # Sort by price and apply highway bonus
    for stop in candidate_stops:
        if "I-" in stop.address:  # Highway accessible
            stop.price_per_gallon -= HIGHWAY_BONUS

    return min(candidate_stops, key=lambda stop: stop.price_per_gallon, default=None)


def calculate_route_segments(
    route: Route, gas_stops: list[GasStop]
) -> list[RouteSegment]:
    segments = []
    cumulative_distances = calculate_cumulative_distances(route.geometry)

    all_points = [route.origin_coordinates]
    all_points.extend([stop.coordinates for stop in gas_stops])
    all_points.append(route.destination_coordinates)

    for segment_index in range(len(all_points) - 1):
        start_point = all_points[segment_index]
        end_point = all_points[segment_index + 1]

        distance = calculate_route_segment_distance(
            start_point=start_point,
            end_point=end_point,
            route_points=route.geometry,
            cumulative_distances=cumulative_distances,
        )
        gas_needed = distance / GAS_EFFICIENCY

        segment = RouteSegment(
            start_coordinates=start_point,
            end_coordinates=end_point,
            distance=round(distance, 2),
            gas_needed_gallons=round(gas_needed, 2),
        )
        segments.append(segment)

    return segments


def calculate_route_segment_distance(
    start_point: Coordinates,
    end_point: Coordinates,
    route_points: List[Coordinates],
    cumulative_distances: List[float],
) -> float:
    start_index = find_closest_route_point_index(start_point, route_points)
    end_index = find_closest_route_point_index(end_point, route_points)

    route_distance = cumulative_distances[end_index] - cumulative_distances[start_index]
    return route_distance + DETOUR_ALLOWANCE


def find_closest_route_point_index(
    target_point: Coordinates, route_points: List[Coordinates]
) -> int:
    # Stage 1: Fast Euclidean distance to get top candidates
    candidates = []
    target_lat = target_point.latitude
    target_lon = target_point.longitude

    for point_index, route_point in enumerate(route_points):
        # Fast Euclidean distance calculation
        lat_diff = target_lat - route_point.latitude
        lon_diff = target_lon - route_point.longitude
        euclidean_dist_squared = lat_diff * lat_diff + lon_diff * lon_diff
        candidates.append((euclidean_dist_squared, point_index))

    # Sort and take top 10 candidates
    candidates.sort()
    top_candidates = candidates[:10]

    # Stage 2: Accurate geodesic distance on small set
    best_index = 0
    min_geodesic = float("inf")

    for _, point_index in top_candidates:
        geodesic_dist = geodesic(
            target_point.to_tuple(), route_points[point_index].to_tuple()
        ).miles
        if geodesic_dist < min_geodesic:
            min_geodesic = geodesic_dist
            best_index = point_index

    return best_index


def calculate_total_gas_cost(
    segments: list[RouteSegment], gas_stops: list[GasStop]
) -> float:
    if not gas_stops:
        return 0.0

    total_cost = 0.0
    for segment_index, segment in enumerate(segments):
        if segment_index < len(gas_stops):
            gas_needed = segment.gas_needed_gallons
            price_per_gallon = gas_stops[segment_index].price_per_gallon
            total_cost += gas_needed * price_per_gallon

    return round(total_cost, 2)
