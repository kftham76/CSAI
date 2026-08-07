"""Automated AGM document generation."""

from .generator import generate_documents
from .models import GenerationResult

__all__ = ["GenerationResult", "generate_documents"]
