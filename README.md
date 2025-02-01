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
