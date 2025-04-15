from pyroute2 import IPRoute
import vpp_papi
from abc import ABC, abstractmethod
import os
import ipaddress

class RouteProgrammer(ABC):
    @abstractmethod
    def program_route(self, destination_prefix, srv6_usid, **kwargs):
        pass

    @abstractmethod
    def delete_route(self, destination_prefix, **kwargs):
        pass

class LinuxRouteProgrammer(RouteProgrammer):
    def __init__(self):
        if os.geteuid() != 0:
            raise PermissionError("Root privileges required for route programming. Please run with sudo.")
        self.iproute = IPRoute()

    def _expand_srv6_usid(self, usid):
        """Expand SRv6 USID to full IPv6 address"""
        # Remove any trailing colons
        usid = usid.rstrip(':')
        
        # Split the USID into parts
        parts = usid.split(':')
        
        # Add zeros to make it a complete IPv6 address (8 parts)
        while len(parts) < 8:
            parts.append('0')
            
        return ':'.join(parts)

    def program_route(self, destination_prefix, srv6_usid, **kwargs):
        """Program Linux SRv6 route using pyroute2"""
        try:
            if not destination_prefix:
                raise ValueError("destination_prefix is required")
            if not kwargs.get('outbound_interface'):
                raise ValueError("outbound_interface is required")
            
            # Get table ID, default to main table (254)
            table_id = kwargs.get('table_id', 254)
            
            # Validate and normalize the destination prefix
            try:
                net = ipaddress.ip_network(destination_prefix)
                dst = {'dst': str(net)}
            except ValueError as e:
                raise ValueError(f"Invalid destination prefix: {e}")

            # Validate and normalize the SRv6 USID
            try:
                expanded_usid = self._expand_srv6_usid(srv6_usid)
                ipaddress.IPv6Address(expanded_usid)
            except ValueError as e:
                raise ValueError(f"Invalid SRv6 USID: {e}")
            
            # Get interface index
            if_index = self.iproute.link_lookup(ifname=kwargs.get('outbound_interface'))[0]
            
            # Create encap info
            encap = {'type': 'seg6',
                    'mode': 'encap',
                    'segs': [expanded_usid]}
            
            # Try to delete existing route first
            try:
                self.iproute.route('del', table=table_id, dst=str(net))
                print(f"Deleted existing route to {str(net)} in table {table_id}")
            except Exception as e:
                # Ignore errors if route doesn't exist
                pass
            
            print(f"Adding route with encap: {encap} to table {table_id}")
            
            # Add new route
            self.iproute.route('add',
                             table=table_id,
                             dst=str(net),
                             oif=if_index,
                             encap=encap)
            
            return True, f"Route to {destination_prefix} via {expanded_usid} programmed successfully in table {table_id}"
        except Exception as e:
            return False, f"Failed to program route: {str(e)}"
        
    def delete_route(self, destination_prefix, **kwargs):
        """Delete Linux SRv6 route using pyroute2"""
        try:
            if not destination_prefix:
                raise ValueError("destination_prefix is required")
            
            # Get table ID, default to main table (254)
            table_id = kwargs.get('table_id', 254)
            
            # Validate and normalize the destination prefix
            try:
                net = ipaddress.ip_network(destination_prefix)
            except ValueError as e:
                raise ValueError(f"Invalid destination prefix: {e}")
            
            # Delete the route
            try:
                self.iproute.route('del', table=table_id, dst=str(net))
                return True, f"Route to {destination_prefix} deleted successfully from table {table_id}"
            except Exception as e:
                if "No such process" in str(e):
                    return False, f"Route to {destination_prefix} not found in table {table_id}"
                raise
                
        except Exception as e:
            return False, f"Failed to delete route: {str(e)}"

    def __del__(self):
        if hasattr(self, 'iproute'):
            self.iproute.close()

    def program_l3vpn_route(self, destination_prefix, srv6_usid, vpn_label, **kwargs):
        """Program Linux SRv6 L3VPN route"""
        try:
            if not destination_prefix:
                raise ValueError("destination_prefix is required")
            if not kwargs.get('outbound_interface'):
                raise ValueError("outbound_interface is required")
            if not vpn_label:
                raise ValueError("vpn_label is required for L3VPN routes")
            
            # Get table ID, default to main table (254)
            table_id = kwargs.get('table_id', 254)
            
            # Validate and normalize the destination prefix
            try:
                net = ipaddress.ip_network(destination_prefix)
                dst = {'dst': str(net)}
            except ValueError as e:
                raise ValueError(f"Invalid destination prefix: {e}")

            # Validate and normalize the SRv6 USID
            try:
                expanded_usid = self._expand_srv6_usid(srv6_usid)
                ipaddress.IPv6Address(expanded_usid)
            except ValueError as e:
                raise ValueError(f"Invalid SRv6 USID: {e}")
            
            # Get interface index
            if_index = self.iproute.link_lookup(ifname=kwargs.get('outbound_interface'))[0]
            
            # Create encap info with VPN SID
            # For SRv6 L3VPN, we need to use the DT4/DT6 function with the VPN label
            # Format: <locator>:<function>:<arguments>:<vpn-label>
            # Where function is DT4 or DT6 (Endpoint with decapsulation and IPv4/IPv6 table lookup)
            
            # Extract the locator part (first 4 hextets)
            locator_parts = expanded_usid.split(':')[:4]
            locator = ':'.join(locator_parts)
            
            # Determine if IPv4 or IPv6 based on destination prefix
            dt_function = "dt4" if isinstance(net, ipaddress.IPv4Network) else "dt6"
            
            # Create the VPN SID
            vpn_sid = f"{locator}:{dt_function}:{vpn_label}::"
            
            encap = {'type': 'seg6',
                    'mode': 'encap',
                    'segs': [vpn_sid]}
            
            # Try to delete existing route first
            try:
                self.iproute.route('del', table=table_id, dst=str(net))
                print(f"Deleted existing route to {str(net)} in table {table_id}")
            except Exception as e:
                # Ignore errors if route doesn't exist
                pass
            
            print(f"Adding L3VPN route with encap: {encap} to table {table_id}")
            
            # Add new route
            self.iproute.route('add',
                             table=table_id,
                             dst=str(net),
                             oif=if_index,
                             encap=encap)
            
            return True, f"L3VPN route to {destination_prefix} via {vpn_sid} programmed successfully in table {table_id}"
        except Exception as e:
            return False, f"Failed to program L3VPN route: {str(e)}"

class VPPRouteProgrammer(RouteProgrammer):
    def __init__(self):
        try:
            import subprocess
            self.subprocess = subprocess
            
            # Test VPP CLI access
            result = self.subprocess.run(['vppctl', 'show', 'version'], 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError("Failed to access VPP CLI")
                
            self.version = result.stdout.strip()
            # Only print version if verbose logging is enabled
            if 'VPP_DEBUG' in os.environ:
                print(f"Connected to VPP version: {self.version}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to connect to VPP: {str(e)}")

    def _expand_srv6_usid(self, usid):
        """Expand SRv6 USID to full IPv6 address"""
        # Remove any trailing colons
        usid = usid.rstrip(':')
        
        # Split the USID into parts
        parts = usid.split(':')
        
        # Add zeros to make it a complete IPv6 address (8 parts)
        while len(parts) < 8:
            parts.append('0')
            
        return ':'.join(parts)

    def program_route(self, destination_prefix, srv6_usid, **kwargs):
        """Program VPP SRv6 route using CLI"""
        try:
            bsid = kwargs.get('bsid')
            if not bsid:
                raise ValueError("BSID is required for VPP routes")

            # Validate inputs
            try:
                net = ipaddress.ip_network(destination_prefix)
                expanded_usid = self._expand_srv6_usid(srv6_usid)
            except ValueError as e:
                raise ValueError(f"Invalid input parameters: {str(e)}")

            # Add SR policy
            policy_cmd = f"sr policy add bsid {bsid} next {expanded_usid} encap"
            if 'VPP_DEBUG' in os.environ:
                print(f"Executing: vppctl {policy_cmd}")
            result = self.subprocess.run(['vppctl'] + policy_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to add SR policy: {result.stderr}")

            # Add steering policy
            steer_cmd = f"sr steer l3 {destination_prefix} via bsid {bsid}"
            if 'VPP_DEBUG' in os.environ:
                print(f"Executing: vppctl {steer_cmd}")
            result = self.subprocess.run(['vppctl'] + steer_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to add steering policy: {result.stderr}")
            
            return True, f"Route programmed successfully"
        except Exception as e:
            return False, f"Failed to program route: {str(e)}"

    def delete_route(self, destination_prefix, **kwargs):
        """Delete VPP SRv6 route using CLI"""
        try:
            bsid = kwargs.get('bsid')
            if not bsid:
                raise ValueError("BSID is required for VPP routes")

            # Delete steering policy first
            steer_cmd = f"sr steer del l3 {destination_prefix}"
            if 'VPP_DEBUG' in os.environ:
                print(f"Executing: vppctl {steer_cmd}")
            result = self.subprocess.run(['vppctl'] + steer_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to delete steering policy: {result.stderr}")

            # Then delete SR policy
            policy_cmd = f"sr policy del bsid {bsid}"
            if 'VPP_DEBUG' in os.environ:
                print(f"Executing: vppctl {policy_cmd}")
            result = self.subprocess.run(['vppctl'] + policy_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to delete SR policy: {result.stderr}")
            
            return True, f"Route deleted successfully"
        except Exception as e:
            return False, f"Failed to delete route: {str(e)}"

    def __del__(self):
        pass  # No cleanup needed for CLI approach

    def program_l3vpn_route(self, destination_prefix, srv6_usid, vpn_label, **kwargs):
        """Program VPP SRv6 L3VPN route"""
        try:
            bsid = kwargs.get('bsid')
            if not bsid:
                raise ValueError("BSID is required for VPP routes")
            if not vpn_label:
                raise ValueError("vpn_label is required for L3VPN routes")

            # Validate inputs
            try:
                net = ipaddress.ip_network(destination_prefix)
                expanded_usid = self._expand_srv6_usid(srv6_usid)
            except ValueError as e:
                raise ValueError(f"Invalid input parameters: {str(e)}")

            # Extract the locator part (first 4 hextets)
            locator_parts = expanded_usid.split(':')[:4]
            locator = ':'.join(locator_parts)
            
            # Determine if IPv4 or IPv6 based on destination prefix
            dt_function = "DT4" if isinstance(net, ipaddress.IPv4Network) else "DT6"
            
            # Create the VPN SID
            vpn_sid = f"{locator}:{dt_function}:{vpn_label}::"

            # Add SR policy with VPN SID
            policy_cmd = f"sr policy add bsid {bsid} next {vpn_sid} encap"
            if 'VPP_DEBUG' in os.environ:
                print(f"Executing: vppctl {policy_cmd}")
            result = self.subprocess.run(['vppctl'] + policy_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to add SR policy: {result.stderr}")

            # Add steering policy
            table_id = kwargs.get('table_id', 0)
            steer_cmd = f"sr steer l3 {destination_prefix} via bsid {bsid} table {table_id}"
            if 'VPP_DEBUG' in os.environ:
                print(f"Executing: vppctl {steer_cmd}")
            result = self.subprocess.run(['vppctl'] + steer_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to add steering policy: {result.stderr}")
            
            return True, f"L3VPN route programmed successfully"
        except Exception as e:
            return False, f"Failed to program L3VPN route: {str(e)}"

class RouteProgrammerFactory:
    @staticmethod
    def get_programmer(platform):
        if platform.lower() == 'linux':
            return LinuxRouteProgrammer()
        elif platform.lower() == 'vpp':
            return VPPRouteProgrammer()
        else:
            raise ValueError(f"Unsupported platform: {platform}") 