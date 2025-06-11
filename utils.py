def generate_google_map_html(pin_coords, google_key):
    pin_markers = [
        f"new google.maps.Marker({{ position: {{ lat: {lat}, lng: {lng} }}, map: map, title: '{city}' }});"
        for city, (lat, lng) in pin_coords.items() if lat is not None and lng is not None
    ]

    return f"""
    <div id='map' style='height: 600px; width: 100%; margin-bottom: 20px;'></div>
    <script src='https://maps.googleapis.com/maps/api/js?key={google_key}'></script>
    <script>
    function initMap() {{
        const map = new google.maps.Map(document.getElementById('map'), {{
            zoom: 5,
            center: {{ lat: 50.0, lng: -100.0 }}
        }});
        {''.join(pin_markers)}
    }}
    window.onload = initMap;
    </script>
    """
