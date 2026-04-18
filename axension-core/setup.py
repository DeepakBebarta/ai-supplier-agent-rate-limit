"""
Install (from any agent repo):
    pip install -e ../axension-core

Or in requirements-dev.txt:
    -e ../axension-core
"""
from setuptools import setup, find_packages

setup(
    name="axension-core",
    version="0.5.0",
    description="Shared WhatsApp messaging + utilities for Axension AI agents",
    author="Axension AI",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "axension_core.messaging": ["templates/*.j2"],
    },
    install_requires=[
        "redis>=5.0.0",
        "requests>=2.31.0",
        "Jinja2>=3.1.0",
        "psycopg[binary]>=3.1.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0.0", "fakeredis>=2.20.0"],
    },
    python_requires=">=3.10",
)
