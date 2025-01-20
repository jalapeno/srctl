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
                self.iproute.route('del', dst=str(net))
                print(f"Deleted existing route to {str(net)}")
            except Exception as e:
                # Ignore errors if route doesn't exist
                pass
            
            print(f"Adding route with encap: {encap}")
            
            # Add new route
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
        try:
            from vpp_papi import VPPApiClient
            self.vpp = VPPApiClient()
            self.vpp.connect("srctl")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to VPP: {str(e)}")

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

            # Convert string addresses to binary format
            bsid_addr = ipaddress.IPv6Address(bsid).packed
            srv6_usid_addr = ipaddress.IPv6Address(srv6_usid).packed

            # Add SR policy
            self.vpp.sr_policy_add_v2(
                bsid_addr=bsid_addr,
                sids={'weight': 1, 'segments': [srv6_usid_addr]},
                is_encap=1,
                is_spray=0,
                type=0
            )

            # Add steering policy
            prefix_addr = ipaddress.IPv6Address(str(net.network_address)).packed
            self.vpp.sr_steering_add_del(
                is_del=0,
                bsid_addr=bsid_addr,
                sr_policy_index=0,  # Not used when bsid is specified
                table_id=0,
                prefix_addr=prefix_addr,
                prefix_len=net.prefixlen,
                sw_if_index=4294967295,  # INVALID_INDEX for L3 traffic
                traffic_type=3  # L3 traffic
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