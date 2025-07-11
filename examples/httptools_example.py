import httptools
import asyncio


class HTTPToolsParser:
    def __init__(self):
        self.reset()

    def reset(self):
        self.headers = {}
        self.body = b""
        self.url = None
        self.method = None
        self.should_keep_alive = False
        self.complete = False

        # Create parser with callbacks
        self.parser = httptools.HttpRequestParser(self)

    # Required callback methods
    def on_message_begin(self):
        """Called when request parsing begins"""
        pass

    def on_url(self, url: bytes):
        """Called when URL is parsed"""
        self.url = url.decode()

    def on_header(self, name: bytes, value: bytes):
        """Called for each header"""
        self.headers[name.decode().lower()] = value.decode()

    def on_headers_complete(self):
        """Called when headers are complete"""
        self.method = self.parser.get_method().decode()
        self.should_keep_alive = self.parser.should_keep_alive()

    def on_body(self, body: bytes):
        """Called for body chunks"""
        self.body += body

    def on_message_complete(self):
        """Called when request is complete"""
        self.complete = True

    def feed_data(self, data: bytes):
        """Feed data to parser"""
        try:
            self.parser.feed_data(data)
        except httptools.HttpParserError as e:
            raise ValueError(f"HTTP parsing error: {e}")

    def get_request_data(self):
        """Get parsed request data"""
        return {
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "body": self.body,
            "keep_alive": self.should_keep_alive,
        }
