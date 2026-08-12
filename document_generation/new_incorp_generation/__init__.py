"""New-incorporation document-generation package."""

from .context_builder import prepare_new_incorp_generation
from .generator import generate_new_incorp_documents

__all__ = [
    "generate_new_incorp_documents",
    "prepare_new_incorp_generation",
]
