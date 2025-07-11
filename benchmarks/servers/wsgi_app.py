import json


def app(environ, start_response):
    """Simple WSGI application for benchmarking."""
    status = "200 OK"
    headers = [("Content-Type", "application/json")]

    # Get payload size from query string if provided
    try:
        payload_size = int(environ.get("QUERY_STRING", "").split("=")[1])
    except (IndexError, ValueError):
        payload_size = 1024  # Default size

    # Generate response payload
    response = {
        "message": "Hello from benchmark server!",
        "data": "X" * max(0, payload_size - 50),  # Adjust for JSON overhead
    }

    start_response(status, headers)
    return [json.dumps(response).encode()]
