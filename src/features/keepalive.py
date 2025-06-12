import asyncio

class KeepAliveHandler:
    def __init__(self, handler, max_requests=1000):
        self.handler = handler
        self.max_requests = max_requests
    
    async def handle_connection(self, reader, writer):
        requests_handled = 0
        
        while requests_handled < self.max_requests:
            try:
                # Check if connection is still alive
                if reader.at_eof():
                    break
                
                await self.handler.handle_request(reader, writer)
                requests_handled += 1
                
                # Check Connection header for keep-alive
                # In a full implementation, you'd parse this from the request
                # For now, we'll assume keep-alive unless client closes
                
            except asyncio.IncompleteReadError:
                break
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"Keep-alive error: {e}")
                break
        
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass