# jalactl

## Usage

# Using default API server (http://localhost:8000)
```
jalactl apply -f rome.yaml
```

# Specifying custom API server

```
jalactl --api-server http://api.jalapeno.example.com:8000 apply -f rome.yaml
```

# Using environment variable

```
export JALAPENO_API_SERVER=http://api.jalapeno.example.com:8080
jalactl apply -f rome.yaml
```