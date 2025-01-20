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
            
            # Validate and normalize the destination prefix
            try:
                net = ipaddress.ip_network(destination_prefix)
                dst = {'dst': str(net)}
            except ValueError as e:
                raise ValueError(f"Invalid destination prefix: {e}")

            # Validate and normalize the SRv6 USID
            try:
                expanded_usid = self._expand_srv6_usid(srv6_usid)
                # Validate as an IPv6 address
                ipaddress.IPv6Address(expanded_usid)
            except ValueError as e:
                raise ValueError(f"Invalid SRv6 USID: {e}")
            
            # Get interface index
            if_index = self.iproute.link_lookup(ifname=kwargs.get('outbound_interface'))[0]
            
            # Create encap info
            encap = {'type': 'seg6',
                    'mode': 'encap',
                    'segs': [expanded_usid]}
            
            print(f"Adding route with encap: {encap}")  # Debug print
            
            # Add route
            self.iproute.route('add',
                             dst=str(net),
                             oif=if_index,
                             encap=encap)
            
            return True, f"Route to {destination_prefix} via {expanded_usid} programmed successfully"
        except Exception as e:
            return False, f"Failed to program route: {str(e)}"
        
    def __del__(self):
        if hasattr(self, 'iproute'):
            self.iproute.close()

class VPPRouteProgrammer(RouteProgrammer):
    def __init__(self):
        self.vpp = vpp_papi.VPP()
        self.vpp.connect("jalactl")

    def program_route(self, destination_prefix, srv6_usid, **kwargs):
        """Program VPP SRv6 route using vpp_papi"""
        try:
            bsid = kwargs.get('bsid')
            if not bsid:
                raise ValueError("BSID is required for VPP routes")

            # Validate the destination prefix
            try:
                net = ipaddress.ip_network(destination_prefix)
            except ValueError as e:
                raise ValueError(f"Invalid destination prefix: {e}")

            # Validate the SRv6 USID
            try:
                srv6_usid = srv6_usid.rstrip(':')
                ipaddress.IPv6Address(srv6_usid)
            except ValueError as e:
                raise ValueError(f"Invalid SRv6 USID: {e}")

            # Add SR policy
            self.vpp.sr_policy_add(
                bsid=bsid,
                segments=[srv6_usid],
                is_encap=1
            )

            # Add steering policy
            self.vpp.sr_steering_add_del(
                is_del=0,
                traffic_type=3,  # L3 traffic
                prefix=str(net),
                sr_policy_index=bsid
            )
            
            return True, f"Route to {destination_prefix} via {srv6_usid} programmed successfully"
        except Exception as e:
            return False, f"Failed to program route: {str(e)}"

    def __del__(self):
        if hasattr(self, 'vpp'):
            self.vpp.disconnect()

class RouteProgrammerFactory:
    @staticmethod
    def get_programmer(platform):
        if platform.lower() == 'linux':
            return LinuxRouteProgrammer()
        elif platform.lower() == 'vpp':
            return VPPRouteProgrammer()
        else:
            raise ValueError(f"Unsupported platform: {platform}") 