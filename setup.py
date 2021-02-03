from distutils.core import setup

setup(
    name="zipget",
    version="1.0.0",
    description="Download and unzip things",
    author="Ville M. Vainio",
    author_email="ville.vainio@basware.com",
    url="https://github.com/vivainio/zipget",
    packages=["zipget"],
    install_requires=[],
    entry_points={"console_scripts": ["zipget = zipget.zipget:main"]},
)
