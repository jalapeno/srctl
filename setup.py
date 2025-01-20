from setuptools import setup, find_packages

setup(
    name="jalactl",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "requests",
        "pyyaml",
    ],
    entry_points={
        "console_scripts": [
            "jalactl=jalactl.cli:main",
        ],
    },
) 