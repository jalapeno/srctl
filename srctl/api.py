import requests
from urllib.parse import urlencode
from .route_programmer import RouteProgrammerFactory

class JalapenoAPI:
    def __init__(self, config):
        self.config = config

    def apply(self, data):
        """Send configuration to Jalapeno API"""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid configuration format: expected dict, got {type(data)}")
            
        if data.get('kind') == 'PathRequest':
            return self._handle_path_requests(data)
        else:
            raise ValueError(f"Unsupported resource kind: {data.get('kind')}")

    def _handle_path_requests(self, data):
        """Handle multiple PathRequest resources"""
        spec = data.get('spec', [])
        if not spec:
            raise ValueError("No path requests found in spec")
            
        results = []
        
        for path_request in spec:
            try:
                if not isinstance(path_request, dict):
                    raise ValueError(f"Invalid path request format: {path_request}")
                
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
                print(f"Making request to: {final_url}")  # Debug print
                
                # Make the request
                response = requests.get(final_url)
                if not response.ok:
                    error_msg = f"API request failed with status {response.status_code}: {response.text}"
                    print(f"API Error: {error_msg}")  # Debug print
                    raise requests.exceptions.RequestException(error_msg)
                
                response_data = response.json()
                srv6_usid = response_data.get('srv6_data', {}).get('srv6_usid')
                
                if 'platform' in path_request:
                    try:
                        # Program the route
                        programmer = RouteProgrammerFactory.get_programmer(path_request['platform'])
                        success, message = programmer.program_route(
                            destination_prefix=path_request.get('destination_prefix'),
                            srv6_usid=srv6_usid,
                            outbound_interface=path_request.get('outbound_interface'),
                            bsid=path_request.get('bsid')
                        )
                        
                        if not success:
                            raise Exception(f"Route programming failed: {message}")
                        
                        results.append({
                            'name': path_request['name'],
                            'status': 'success',
                            'data': response_data,
                            'route_programming': message
                        })
                    except Exception as e:
                        print(f"Route Programming Error: {str(e)}")  # Debug print
                        raise
                else:
                    results.append({
                        'name': path_request['name'],
                        'status': 'success',
                        'data': response_data
                    })
                    
            except Exception as e:
                results.append({
                    'name': path_request.get('name', 'unknown'),
                    'status': 'error',
                    'error': f"Error: {str(e)}"
                })
        
        return results 