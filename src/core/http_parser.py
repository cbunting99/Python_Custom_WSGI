import httptools

class HTTPParser:
    def __init__(self):
        self.parser = httptools.HttpRequestParser(self)
        self.headers = {}
        self.body = b''
        self.url = None
        self.method = None
        
    def on_message_begin(self):
        self.headers.clear()
        self.body = b''
        
    def on_url(self, url):
        self.url = url
        
    def on_header(self, name, value):
        self.headers[name.decode()] = value.decode()
        
    def on_body(self, body):
        self.body += body
        
    def on_message_complete(self):
        # Request parsing complete
        pass