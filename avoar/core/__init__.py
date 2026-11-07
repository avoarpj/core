"""Avoar Core: source utilities and generated contracts share this package."""
from pkgutil import extend_path

# Editable installs keep utilities in the checkout and contracts in site-packages.
__path__ = extend_path(__path__, __name__)
