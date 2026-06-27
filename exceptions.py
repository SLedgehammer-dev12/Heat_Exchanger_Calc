from __future__ import annotations


class HeatExchangerError(Exception):
    """Base exception for all heat exchanger calculation errors."""


class InvalidInputError(HeatExchangerError, ValueError):
    """Non-physical or invalid input parameters."""


class InvalidFlowTypeError(InvalidInputError):
    """Unsupported or disallowed flow type for the selected exchanger."""


class InvalidExchangerTypeError(InvalidInputError):
    """Unsupported or unknown exchanger type."""


class InvalidGeometryError(InvalidInputError):
    """Invalid geometry configuration (e.g. D_shell < D_o, non-positive dimensions)."""


class FluidPropertyError(HeatExchangerError, ValueError):
    """Fluid property retrieval or computation failure."""


class ConvergenceError(HeatExchangerError, ValueError):
    """Numerical solver convergence failure (e.g. epsilon out of bounds, zero Nu)."""


class MissingDependencyError(HeatExchangerError, ImportError):
    """Optional dependency not installed (thermo, iapws, pychemengg)."""


class UpdaterError(HeatExchangerError):
    """Release download or verification failure (network, SHA256 mismatch)."""
