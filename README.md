# srctl

## Install srctl

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