from pyroute2 import IPRoute
import vpp_papi
from abc import ABC, abstractmethod
import os
import ipaddress

class RouteProgrammer(ABC):
    @abstractmethod
    def program_route(self, destination_prefix, srv6_usid, **kwargs):
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
        
    def __del__(self):
        if hasattr(self, 'iproute'):
            self.iproute.close()

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

            # Validate the destination prefix
            try:
                net = ipaddress.ip_network(destination_prefix)
            except ValueError as e:
                raise ValueError(f"Invalid destination prefix: {e}")

            # Validate and expand the SRv6 USID
            try:
                expanded_usid = self._expand_srv6_usid(srv6_usid)
            except ValueError as e:
                raise ValueError(f"Invalid SRv6 USID: {e}")

            # First, add the SR policy
            policy_cmd = f"sr policy add bsid {bsid} next {expanded_usid} encap"
            print(f"Executing: vppctl {policy_cmd}")
            result = self.subprocess.run(['vppctl'] + policy_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to add SR policy: {result.stderr}")

            # Then, add the steering policy
            steer_cmd = f"sr steer l3 {destination_prefix} via bsid {bsid}"
            print(f"Executing: vppctl {steer_cmd}")
            result = self.subprocess.run(['vppctl'] + steer_cmd.split(), 
                                      capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to add steering policy: {result.stderr}")
            
            return True, f"Route to {destination_prefix} via {expanded_usid} programmed successfully"
        except Exception as e:
            return False, f"Failed to program route: {str(e)}"

    def __del__(self):
        pass  # No cleanup needed for CLI approach

class RouteProgrammerFactory:
    @staticmethod
    def get_programmer(platform):
        if platform.lower() == 'linux':
            return LinuxRouteProgrammer()
        elif platform.lower() == 'vpp':
            return VPPRouteProgrammer()
        else:
            raise ValueError(f"Unsupported platform: {platform}") 