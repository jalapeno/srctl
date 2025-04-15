import requests
from urllib.parse import urlencode
from .route_programmer import RouteProgrammerFactory

class JalapenoAPI:
    def __init__(self, config):
        self.config = config
        self.debug = False  # Can be set via environment variable if needed

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
        spec = data.get('spec', {})
        if not spec:
            raise ValueError("No spec found in configuration")
            
        results = []
        platform = spec.get('platform')
        if not platform:
            raise ValueError("Platform must be specified in spec")

        # Process default VRF/table routes
        default_vrf = spec.get('defaultVrf', {})
        results.extend(self._process_address_family(default_vrf.get('ipv4', {}), platform, 'ipv4', table_id=0))
        results.extend(self._process_address_family(default_vrf.get('ipv6', {}), platform, 'ipv6', table_id=0))

        # Process VRF/table-specific routes
        for vrf in spec.get('vrfs', []):
            vrf_name = vrf.get('name')
            # Make tableId optional with default value of 0
            table_id = vrf.get('tableId', 0)
            
            # Create VRF if requested
            if vrf.get('createVrf', False):
                programmer = RouteProgrammerFactory.get_programmer(platform)
                success, message = programmer.create_vrf(vrf_name, table_id, 
                                                       rd=vrf.get('rd'),
                                                       import_rts=vrf.get('importRts', []),
                                                       export_rts=vrf.get('exportRts', []))
                
                if not success:
                    results.append({
                        'name': f"VRF {vrf_name}",
                        'status': 'error',
                        'error': message
                    })
                    continue
                
                results.append({
                    'name': f"VRF {vrf_name}",
                    'status': 'success',
                    'message': message
                })
            
            # Process VRF routes
            results.extend(self._process_address_family(vrf.get('ipv4', {}), platform, 'ipv4', 
                                                      table_id=table_id, vrf_name=vrf_name, 
                                                      is_l3vpn=True))
            results.extend(self._process_address_family(vrf.get('ipv6', {}), platform, 'ipv6', 
                                                      table_id=table_id, vrf_name=vrf_name,
                                                      is_l3vpn=True))
        
        return results

    def _process_address_family(self, af_config, platform, af_type, table_id, vrf_name=None):
        """Process routes for a specific address family"""
        results = []
        routes = af_config.get('routes', [])
        
        # Define metric mapping from kebab-case to API endpoints
        metric_mapping = {
            'low-latency': 'latency',
            'least-utilized': 'utilization',
            'data-sovereignty': 'sovereignty'
        }
        
        for route in routes:
            try:
                if not isinstance(route, dict):
                    raise ValueError(f"Invalid route format: {route}")
                
                # Add table_id to route configuration
                route['table_id'] = table_id
                if vrf_name:
                    route['vrf_name'] = vrf_name
                
                # Check if this is an L3VPN route with route_target
                if 'route_target' in route:
                    # This is an L3VPN route lookup
                    collection = route.get('collection', f'l3vpn_{af_type}_prefix')
                    
                    if 'prefix' in route:
                        # Query for specific prefix
                        prefix_data = self.get_l3vpn_prefix(
                            prefix=route['prefix'],
                            route_target=route['route_target'],
                            collection=collection,
                            exact_match=route.get('exact_match', False)
                        )
                    else:
                        # Query for all prefixes in route target
                        prefix_data = self.get_l3vpn_prefixes_by_rt(
                            route_target=route['route_target'],
                            collection=collection
                        )
                    
                    # Apply the routes
                    l3vpn_results = self.apply_l3vpn_routes(
                        platform=platform,
                        prefixes_data=prefix_data,
                        table_id=table_id,
                        outbound_interface=route.get('outbound_interface'),
                        bsid=route.get('bsid')
                    )
                    
                    results.extend(l3vpn_results)
                    continue
                
                # Regular path-based route processing
                if 'graph' not in route:
                    raise ValueError("'graph' is required for path-based routes")
                    
                # Build the base URL with optional metric
                base_url = f"{self.config.base_url}/api/v1/graphs/{route['graph']}/shortest_path"
                if 'metric' in route:
                    # Map the metric name to API endpoint
                    api_metric = metric_mapping.get(route['metric'])
                    if not api_metric:
                        raise ValueError(f"Unsupported metric: {route['metric']}")
                    base_url = f"{base_url}/{api_metric}"
                
                # Add query parameters
                params = {
                    'source': route['source'],
                    'destination': route['destination'],
                    'direction': route.get('direction', 'outbound')  # Default to outbound
                }
                
                # Add sovereignty-specific parameters
                if route.get('metric') == 'data-sovereignty' and 'excluded_countries' in route:
                    params['excluded_countries'] = ','.join(route['excluded_countries'])
                
                # Make the request
                final_url = f"{base_url}?{urlencode(params)}"
                response = requests.get(final_url)
                if not response.ok:
                    raise requests.exceptions.RequestException(
                        f"API request failed with status {response.status_code}: {response.text}"
                    )
                
                response_data = response.json()
                srv6_data = response_data.get('srv6_data', {})
                srv6_usid = srv6_data.get('srv6_usid')
                
                if not srv6_usid:
                    raise ValueError("No SRv6 USID received from API")
                
                # Program the route
                programmer = RouteProgrammerFactory.get_programmer(platform)
                success, message = programmer.program_route(
                    destination_prefix=route.get('destination_prefix'),
                    srv6_usid=srv6_usid,
                    outbound_interface=route.get('outbound_interface'),
                    bsid=route.get('bsid'),
                    table_id=table_id
                )
                
                if not success:
                    raise Exception(f"Route programming failed: {message}")
                
                results.append({
                    'name': route['name'],
                    'status': 'success',
                    'data': response_data,
                    'route_programming': message
                })
                    
            except Exception as e:
                results.append({
                    'name': route.get('name', 'unknown'),
                    'status': 'error',
                    'error': f"Error: {str(e)}"
                })
        
        return results

    def delete(self, data):
        """Delete configuration from device"""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid configuration format: expected dict, got {type(data)}")
            
        if data.get('kind') == 'PathRequest':
            return self._handle_path_deletions(data)
        else:
            raise ValueError(f"Unsupported resource kind: {data.get('kind')}")

    def _handle_path_deletions(self, data):
        """Handle deletion of PathRequest resources"""
        spec = data.get('spec', {})
        if not spec:
            raise ValueError("No spec found in configuration")
            
        results = []
        platform = spec.get('platform')
        if not platform:
            raise ValueError("Platform must be specified in spec")

        # Process default VRF/table routes
        default_vrf = spec.get('defaultVrf', {})
        results.extend(self._delete_address_family(default_vrf.get('ipv4', {}), platform, 'ipv4', table_id=0))
        results.extend(self._delete_address_family(default_vrf.get('ipv6', {}), platform, 'ipv6', table_id=0))

        # Process VRF/table-specific routes
        for vrf in spec.get('vrfs', []):
            table_id = vrf.get('tableId')
            if table_id is None:
                raise ValueError(f"tableId must be specified for VRF {vrf.get('name')}")
            
            results.extend(self._delete_address_family(vrf.get('ipv4', {}), platform, 'ipv4', table_id=table_id))
            results.extend(self._delete_address_family(vrf.get('ipv6', {}), platform, 'ipv6', table_id=table_id))
        
        return results

    def _delete_address_family(self, af_config, platform, af_type, table_id):
        """Delete routes for a specific address family"""
        results = []
        routes = af_config.get('routes', [])
        
        for route in routes:
            try:
                if not isinstance(route, dict):
                    raise ValueError(f"Invalid route format: {route}")
                
                # Program route deletion
                programmer = RouteProgrammerFactory.get_programmer(platform)
                success, message = programmer.delete_route(
                    destination_prefix=route.get('destination_prefix'),
                    bsid=route.get('bsid'),
                    table_id=table_id
                )
                
                if not success:
                    raise Exception(f"Route deletion failed: {message}")
                
                results.append({
                    'name': route['name'],
                    'status': 'success',
                    'message': message
                })
                    
            except Exception as e:
                results.append({
                    'name': route.get('name', 'unknown'),
                    'status': 'error',
                    'error': f"Error: {str(e)}"
                })
        
        return results

    def get_paths(self, source, destination, graph='ipv6_graph', path_type='best-paths', 
                 direction='outbound', limit=None, same_hop_limit=None, plus_one_limit=None):
        """Get best paths between source and destination"""
        try:
            # Build the base URL
            base_url = f"{self.config.base_url}/api/v1/graphs/{graph}/shortest_path/{path_type}"
            
            # Build parameters
            params = {
                'source': source,
                'destination': destination,
                'direction': direction
            }
            
            # Add optional parameters
            if path_type == 'best-paths' and limit is not None:
                params['limit'] = limit
            elif path_type == 'next-best-path':
                if same_hop_limit is not None:
                    params['same_hop_limit'] = same_hop_limit
                if plus_one_limit is not None:
                    params['plus_one_limit'] = plus_one_limit
            
            response = requests.get(f"{base_url}", params=params)
            
            if not response.ok:
                raise requests.exceptions.RequestException(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
            
            return response.json()
            
        except Exception as e:
            raise Exception(f"Failed to get paths: {str(e)}")

    def get_paths_from_yaml(self, config):
        """Get paths from YAML configuration"""
        results = []
        try:
            if 'spec' not in config:
                raise ValueError("Missing 'spec' in configuration")
            
            spec = config['spec']
            if 'defaultVrf' not in spec:
                raise ValueError("Missing 'defaultVrf' in spec")
            
            vrf = spec['defaultVrf']
            
            for ip_version in ['ipv4', 'ipv6']:
                if ip_version in vrf:
                    routes = vrf[ip_version].get('routes', [])
                    
                    for route in routes:
                        try:
                            path_result = self.get_paths(
                                source=route['source'],
                                destination=route['destination'],
                                graph=route.get('graph', 'ipv6_graph'),
                                path_type=route.get('path_type', 'best-paths'),
                                direction=route.get('direction', 'outbound'),
                                limit=route.get('limit'),
                                same_hop_limit=route.get('same_hop_limit'),
                                plus_one_limit=route.get('plus_one_limit')
                            )
                            
                            results.append({
                                'name': route.get('name', f"{route['source']}-to-{route['destination']}"),
                                'status': 'success',
                                'data': path_result
                            })
                        except Exception as e:
                            results.append({
                                'name': route.get('name', f"{route['source']}-to-{route['destination']}"),
                                'status': 'error',
                                'error': str(e)
                            })
            
            return results
            
        except Exception as e:
            raise Exception(f"Failed to process YAML configuration: {str(e)}")

    def get_l3vpn_prefixes_by_rt(self, route_target, collection='l3vpn_v4_prefix', limit=100):
        """Get all L3VPN prefixes for a specific route target"""
        try:
            url = f"{self.config.base_url}/api/v1/vpns/{collection}/prefixes/by-rt"
            params = {
                'route_target': route_target,
                'limit': limit
            }
            
            response = requests.get(url, params=params)
            if not response.ok:
                raise requests.exceptions.RequestException(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
            
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to get L3VPN prefixes by route target: {str(e)}")

    def get_l3vpn_prefix(self, prefix, route_target, collection='l3vpn_v4_prefix', exact_match=False):
        """Get a specific L3VPN prefix for a route target"""
        try:
            url = f"{self.config.base_url}/api/v1/vpns/{collection}/prefixes/search"
            params = {
                'prefix': prefix,
                'route_target': route_target,
                'prefix_exact': 'true' if exact_match else 'false'
            }
            
            response = requests.get(url, params=params)
            if not response.ok:
                raise requests.exceptions.RequestException(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
            
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to get L3VPN prefix: {str(e)}")

    def apply_l3vpn_routes(self, platform, prefixes_data, table_id=None, outbound_interface=None, bsid=None):
        """Apply L3VPN routes from API response data"""
        results = []
        
        # Get the programmer for the specified platform
        programmer = RouteProgrammerFactory.get_programmer(platform)
        
        # Process each prefix in the response
        for prefix_data in prefixes_data.get('prefixes', []):
            try:
                # Extract prefix information
                prefix = prefix_data.get('prefix')
                prefix_len = prefix_data.get('prefix_len')
                destination_prefix = f"{prefix}/{prefix_len}"
                
                # Get SID - handle both string and array formats
                sid = prefix_data.get('sid')
                if isinstance(sid, list) and sid:
                    sid = sid[0]  # Take the first SID if it's an array
                
                if not sid:
                    raise ValueError(f"No SID found for prefix {destination_prefix}")
                
                # Get VPN label
                labels = prefix_data.get('labels', [])
                if not labels:
                    raise ValueError(f"No label found for prefix {destination_prefix}")
                vpn_label = labels[0]
                
                # Program the route
                success, message = programmer.program_l3vpn_route(
                    destination_prefix=destination_prefix,
                    srv6_usid=sid,  # Use the SID directly
                    vpn_label=vpn_label,
                    outbound_interface=outbound_interface,
                    bsid=bsid,
                    table_id=table_id or 0
                )
                
                if not success:
                    raise Exception(f"Route programming failed: {message}")
                
                results.append({
                    'name': f"L3VPN-{destination_prefix}",
                    'status': 'success',
                    'data': prefix_data,
                    'route_programming': message
                })
                    
            except Exception as e:
                results.append({
                    'name': f"L3VPN-{prefix_data.get('prefix', 'unknown')}",
                    'status': 'error',
                    'error': f"Error: {str(e)}"
                })
        
        return results 