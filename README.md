# srctl

## Install srctl

1. cd into srctl directory
```
cd srctl
```

2. Install srctl
```
pip install -e .
su -
pip install -e /home/cisco/srctl
```

## Usage

# Using default API server (http://localhost:8000)
```
srctl apply -f rome.yaml
```

# Specifying custom API server

```
srctl --api-server http://api.jalapeno.example.com:8000 apply -f rome.yaml
```

# Using environment variable

```
export JALAPENO_API_SERVER=http://api.jalapeno.example.com:8080
srctl apply -f rome.yaml
```

For verbose vpp debugging:
```
export VPP_DEBUG=1
sudo srctl --api-server http://198.18.128.101:30800 apply -f examples/amsterdam.yaml
sudo srctl --api-server http://198.18.128.101:30800 apply -f examples/rome.yaml

sudo srctl --api-server http://198.18.128.101:30800 delete -f examples/amsterdam.yaml
sudo srctl --api-server http://198.18.128.101:30800 delete -f examples/rome.yaml

```

# Get paths
```
sudo srctl --api-server http://198.18.128.101:30800 get -f examples/test-paths.yaml
```

# Get paths without yaml or api server
```
srctl get-paths -s hosts/berlin-k8s -d hosts/rome --type next-best-path -v
srctl get-paths -s hosts/berlin-k8s -d hosts/rome --type best-paths --limit 4 -v
srctl get-paths -s hosts/berlin-k8s -d hosts/rome --type next-best-path --same-hop-limit 2 --plus-one-limit 1 -v
```

# more get paths:
```
 srctl get-paths -s igp_node/2_0_0_0000.0000.0001 -d igp_node/2_0_0_0000.0000.0007 --type best-paths
 ```


 # l3vpn routes using CLI args
 ```
 # Get and apply a specific L3VPN prefix
sudo srctl l3vpn get-routes --route-target 15:15 --prefix 15.15.15.0 --platform linux --outbound-interface ens4 --apply

# Get and apply all prefixes for a route-target
sudo srctl l3vpn get-routes --route-target 9:9 --platform linux --outbound-interface ens4 --apply

# For VPP, use the --bsid parameter instead of --outbound-interface
sudo srctl l3vpn get-routes --route-target 15:15 --platform vpp --bsid fd00:100::1 --apply

# Specify a custom table ID
sudo srctl l3vpn get-routes --route-target 15:15 --platform linux --outbound-interface eth0 --table-id 100 --apply

# Use IPv6 L3VPN collection
sudo srctl l3vpn get-routes --route-target 15:15 --collection l3vpn_v6_prefix --platform linux --outbound-interface eth0 --apply

# Get verbose output without applying routes (just show them)
sudo srctl l3vpn get-routes --route-target 15:15 --verbose --platform linux
```

# l3vpn routes using yaml file
```
# Apply the L3VPN routes from the YAML file
sudo srctl apply -f examples/l3vpn-route.yaml

# Apply with verbose output
sudo srctl apply -f examples/l3vpn-route.yaml -v

# Apply with very verbose output
sudo srctl apply -f examples/l3vpn-route.yaml -vv
```