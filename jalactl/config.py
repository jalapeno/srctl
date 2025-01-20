class Config:
    def __init__(self, api_server):
        self.api_server = api_server.rstrip('/')

    @property
    def base_url(self):
        return self.api_server 