from src.core.wsgi_server import HighPerformanceWSGIServer

def my_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)
    return [b'{"message": "Hello from high-performance WSGI!"}']

if __name__ == '__main__':
    server = HighPerformanceWSGIServer(
        app=my_app,
        host='0.0.0.0',
        port=8000,
        workers=8  # Adjust based on CPU cores
    )
    server.run()