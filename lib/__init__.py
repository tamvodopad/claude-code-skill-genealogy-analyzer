"""
Библиотека для работы с GEDCOM файлами.
"""

from .parser import parse_gedcom
from .models import Person, Family, GedcomData

__all__ = ['parse_gedcom', 'Person', 'Family', 'GedcomData']
