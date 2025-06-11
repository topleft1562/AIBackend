def generate_google_map_html(pin_coords: dict, google_key: str) -> str:
    markers_script = ""
    for city, coords in pin_coords.items():
        if coords is None:
            continue
        lat, lng = coords
        markers_script += f"""
        new google.maps.Marker({{
            position: {{ lat: {lat}, lng: {lng} }},
            map: map,
            title: "{city}"
        }});\n"""

    return f"""
    <div id="map" style="height: 500px; width: 100%; margin-bottom: 20px;"></div>
    <script>
    function initMap() {{
        const map = new google.maps.Map(document.getElementById('map'), {{
            zoom: 5,
            center: {{ lat: 50.0, lng: -100.0 }},
        }});
        {markers_script}
    }}
    </script>
    <script async defer src="https://maps.googleapis.com/maps/api/js?key={google_key}&callback=initMap"></script>
    """
