"""Dry-spell detection (pure domain logic, no I/O)."""

from .detector import DrySpellDetector, DrySpellResult

__all__ = ["DrySpellDetector", "DrySpellResult"]
