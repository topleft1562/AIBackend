def generate_google_map_html(pin_coords, google_key):
    if not pin_coords:
        return ""

    marker_scripts = []
    for city, coords in pin_coords.items():
        if coords:
            lat, lng = coords
            marker_scripts.append(
                f"new google.maps.Marker({{ position: {{ lat: {lat}, lng: {lng} }}, map: map, title: '{city}' }});"
            )

    return f"""
    <div id='map' style='height: 600px; width: 100%; margin-bottom: 20px;'></div>
    <script src='https://maps.googleapis.com/maps/api/js?key={google_key}'></script>
    <script>
    function initMap() {{
        const map = new google.maps.Map(document.getElementById('map'), {{
            zoom: 6,
            center: {{ lat: 50.0, lng: -100.0 }}
        }});
        {''.join(marker_scripts)}
    }}
    window.onload = initMap;
    </script>
    """

def generate_route_map_link(cities):
    base_url = "https://www.google.com/maps/dir/"
    path = "/".join(cities)
    return f"{base_url}{path.replace(' ', '+')}"
