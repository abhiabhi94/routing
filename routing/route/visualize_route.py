import folium

from routing.route.routing import OptimalRoute


def create_route_map(
    route_result: OptimalRoute, origin_city: str, destination_city: str
) -> str:
    if not route_result.route_coordinates:
        return ""

    # Create map centered on the route
    center_lat = sum(coord.latitude for coord in route_result.route_coordinates) / len(
        route_result.route_coordinates
    )
    center_lon = sum(coord.longitude for coord in route_result.route_coordinates) / len(
        route_result.route_coordinates
    )

    map_obj = folium.Map(
        location=[center_lat, center_lon], zoom_start=5, tiles="OpenStreetMap"
    )

    # Add route polyline
    route_points = [
        [coord.latitude, coord.longitude] for coord in route_result.route_coordinates
    ]
    folium.PolyLine(
        route_points,
        color="blue",
        weight=3,
        opacity=0.8,
        popup=f"Route: {origin_city} → {destination_city}",
    ).add_to(map_obj)

    # Add origin marker
    origin_coord = route_result.route_coordinates[0]
    folium.Marker(
        [origin_coord.latitude, origin_coord.longitude],
        popup=f"<b>START</b><br>{origin_city}",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(map_obj)

    # Add destination marker
    dest_coord = route_result.route_coordinates[-1]
    folium.Marker(
        [dest_coord.latitude, dest_coord.longitude],
        popup=f"<b>END</b><br>{destination_city}",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(map_obj)

    # Add top 5 nearby gas stations (non-selected)
    for waypoint_index, nearby_stations in enumerate(route_result.nearby_stations):
        selected_station = (
            route_result.gas_stops[waypoint_index]
            if waypoint_index < len(route_result.gas_stops)
            else None
        )

        # Filter out selected station and sort by price
        alternatives = [
            station
            for station in nearby_stations
            if not (
                selected_station
                and station.truckstop_id == selected_station.truckstop_id
            )
        ]

        # Sort by price and take top 5
        alternatives.sort(key=lambda s: s.price_per_gallon)
        top_alternatives = alternatives[:5]

        for rank, station in enumerate(top_alternatives, 1):
            popup_html = f"""
            <b>❌ Alternative #{rank}</b><br>
            <b>{station.name}</b><br>
            {station.address}<br>
            {station.city}, {station.state}<br>
            <b>Price: ${station.price_per_gallon:.3f}/gallon</b>
            """

            folium.Marker(
                [station.coordinates.latitude, station.coordinates.longitude],
                popup=popup_html,
                icon=folium.Icon(color="gray", icon="remove"),
            ).add_to(map_obj)

    # Add selected gas station markers
    for stop_index, gas_stop in enumerate(route_result.gas_stops, 1):
        popup_html = f"""
        <b>✅ Selected Gas Stop {stop_index}</b><br>
        <b>{gas_stop.name}</b><br>
        {gas_stop.address}<br>
        {gas_stop.city}, {gas_stop.state}<br>
        <b>Price: ${gas_stop.price_per_gallon:.3f}/gallon</b>
        """

        folium.Marker(
            [gas_stop.coordinates.latitude, gas_stop.coordinates.longitude],
            popup=popup_html,
            icon=folium.Icon(color="orange", icon="glyphicon-tint"),
        ).add_to(map_obj)

    # Add invisible segment markers for click info
    for segment_index, segment in enumerate(route_result.segments):
        # Calculate midpoint of segment
        start_lat = segment.start_coordinates.latitude
        start_lon = segment.start_coordinates.longitude
        end_lat = segment.end_coordinates.latitude
        end_lon = segment.end_coordinates.longitude

        mid_lat = (start_lat + end_lat) / 2
        mid_lon = (start_lon + end_lon) / 2

        # Create detailed popup with segment info
        popup_html = f"""
        <b>Segment {segment_index + 1}</b><br>
        <b>Distance:</b> {segment.distance} miles<br>
        <b>Gas needed:</b> {segment.gas_needed_gallons} gallons<br>
        <b>From:</b> {segment.start_coordinates.latitude:.4f}, {segment.start_coordinates.longitude:.4f}<br>
        <b>To:</b> {segment.end_coordinates.latitude:.4f}, {segment.end_coordinates.longitude:.4f}
        """

        # Create a small, clickable circle marker
        folium.CircleMarker(
            [mid_lat, mid_lon],
            radius=8,
            popup=popup_html,
            color="blue",
            fill=True,
            fillColor="lightblue",
            fillOpacity=0.7,
            tooltip=f"Click for Segment {segment_index + 1} info",
        ).add_to(map_obj)

    # Add route info as a legend
    legend_html = f"""
    <div style="position: fixed;
                bottom: 10px; right: 10px; width: 320px; height: auto;
                background-color: white; border:2px solid grey; z-index:9999;
                font-size:14px; padding: 10px">
    <h4>Route Information</h4>
    <b>Total Distance:</b> {route_result.total_distance:.1f} miles<br>
    <b>Total Gas Cost:</b> ${route_result.total_gas_cost:.2f}<br>
    <b>Route:</b> {origin_city} → {destination_city}<br><br>

    <h4>Map Legend</h4>
    <span style="color: orange;">🟠</span> Selected Gas Stations ({len(route_result.gas_stops)})<br>
    <span style="color: gray;">⚫</span> Top 5 Alternatives per Stop<br>
    <span style="color: green;">🟢</span> Start Location<br>
    <span style="color: red;">🔴</span> End Location<br>
    <span style="color: blue;">🔵</span> Route Path<br>
    <span style="color: lightblue;">🔵</span> Click blue circles for segment info
    </div>
    """
    map_obj.get_root().html.add_child(folium.Element(legend_html))

    return map_obj
