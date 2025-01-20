from pyroute2 import IPRoute
import vpp_papi
from abc import ABC, abstractmethod
import os

class RouteProgrammer(ABC):
    @abstractmethod
    def program_route(self, destination_prefix, srv6_usid, **kwargs):
        pass

class LinuxRouteProgrammer(RouteProgrammer):
    def __init__(self):
        if os.geteuid() != 0:
            raise PermissionError("Root privileges required for route programming. Please run with sudo.")
        self.iproute = IPRoute()

    def program_route(self, destination_prefix, srv6_usid, **kwargs):
        """Program Linux SRv6 route using pyroute2"""
        try:
            if not destination_prefix:
                raise ValueError("destination_prefix is required")
            if not kwargs.get('outbound_interface'):
                raise ValueError("outbound_interface is required")
            
            # Get interface index
            if_index = self.iproute.link_lookup(ifname=kwargs.get('outbound_interface'))[0]
            
            # Create encap info
            encap = {'type': 'seg6',
                    'mode': 'encap',
                    'segs': [srv6_usid]}
            
            # Add route
            self.iproute.route('add',
                             dst=destination_prefix,
                             oif=if_index,
                             encap=encap)
            
            return True, f"Route to {destination_prefix} via {srv6_usid} programmed successfully"
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
                prefix=destination_prefix,
                sr_policy_index=bsid
            )
            
            return True, "Route programmed successfully"
        except Exception as e:
            return False, f"Failed to program route: {str(e)}"

    def __del__(self):
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