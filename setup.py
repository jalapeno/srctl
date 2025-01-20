from setuptools import setup, find_packages

setup(
    name="srctl",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "requests",
        "pyyaml",
        "pyroute2",
        "vpp-papi"
    ],
    entry_points={
        "console_scripts": [
            "srctl=srctl.cli:main",
        ],
    },
) 