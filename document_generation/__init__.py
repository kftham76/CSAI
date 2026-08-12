"""Automated AGM document generation."""

from .agm_generation.generator import generate_documents
from .pre_incorp_generation.generator import generate_pre_incorp_documents
from .pre_incorp_generation.preparation import prepare_pre_incorp_generation
from .agm_generation.models import GenerationResult

__all__ = [
    "GenerationResult",
    "generate_documents",
    "generate_pre_incorp_documents",
    "prepare_pre_incorp_generation",
]
