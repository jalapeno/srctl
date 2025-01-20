import requests
from urllib.parse import urlencode

class JalapenoAPI:
    def __init__(self, config):
        self.config = config

    def apply(self, data):
        """Send configuration to Jalapeno API"""
        if data.get('kind') == 'PathRequest':
            return self._handle_path_requests(data)
        else:
            raise ValueError(f"Unsupported resource kind: {data.get('kind')}")

    def _handle_path_requests(self, data):
        """Handle multiple PathRequest resources"""
        spec = data.get('spec', [])
        results = []
        
        for path_request in spec:
            try:
                # Build the base URL with optional metric
                base_url = f"{self.config.base_url}/api/v1/graphs/{path_request['graph']}/shortest_path"
                if 'metric' in path_request:
                    base_url = f"{base_url}/{path_request['metric']}"
                
                # Add query parameters
                params = {
                    'source': path_request['source'],
                    'destination': path_request['destination']
                }
                
                # Construct final URL with query parameters
                final_url = f"{base_url}?{urlencode(params)}"
                
                # Make the request
                response = requests.get(final_url)
                response.raise_for_status()
                
                results.append({
                    'name': path_request['name'],
                    'status': 'success',
                    'data': response.json()
                })
            except Exception as e:
                results.append({
                    'name': path_request['name'],
                    'status': 'error',
                    'error': str(e)
                })
        
        return results 