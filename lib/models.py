"""
Модели данных для GEDCOM.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict, Set


@dataclass
class Person:
    """Персона в генеалогическом древе."""
    id: str
    name: str = ""
    given_name: str = ""  # Имя (GIVN)
    surname: str = ""     # Фамилия (SURN)
    patronymic: str = ""  # Отчество (извлечено из имени)
    sex: str = ""         # M/F

    # Даты
    birth_date: Optional[date] = None
    birth_year: Optional[int] = None
    birth_place: str = ""
    birth_is_julian: bool = False

    death_date: Optional[date] = None
    death_year: Optional[int] = None
    death_place: str = ""
    death_cause: str = ""
    death_is_julian: bool = False

    christening_date: Optional[date] = None
    christening_is_julian: bool = False

    # Связи с семьями
    famc: Optional[str] = None  # Семья где персона - ребёнок
    fams: List[str] = field(default_factory=list)  # Семьи где персона - супруг

    # Дополнительно
    occupation: str = ""
    residence: List[Dict] = field(default_factory=list)  # [{place, date_from, date_to, lat, lon}]
    godparents: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def age_at_death(self) -> Optional[int]:
        """Возраст на момент смерти."""
        if self.death_year and self.birth_year:
            return self.death_year - self.birth_year
        if self.death_date and self.birth_date:
            years = self.death_date.year - self.birth_date.year
            if (self.death_date.month, self.death_date.day) < (self.birth_date.month, self.birth_date.day):
                years -= 1
            return years
        return None

    def is_alive(self) -> bool:
        """Жив ли человек (нет записи о смерти)."""
        return self.death_date is None and self.death_year is None


@dataclass
class Family:
    """Семья (брак) в генеалогическом древе."""
    id: str
    husband_id: Optional[str] = None
    wife_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)

    # Брак
    marriage_date: Optional[date] = None
    marriage_year: Optional[int] = None
    marriage_place: str = ""
    marriage_is_julian: bool = False

    # Развод
    divorce_date: Optional[date] = None


@dataclass
class GedcomData:
    """Полные данные из GEDCOM файла."""
    persons: Dict[str, Person] = field(default_factory=dict)
    families: Dict[str, Family] = field(default_factory=dict)

    def get_person(self, person_id: str) -> Optional[Person]:
        """Получить персону по ID."""
        return self.persons.get(person_id)

    def get_family(self, family_id: str) -> Optional[Family]:
        """Получить семью по ID."""
        return self.families.get(family_id)

    def get_parents(self, person: Person) -> tuple:
        """Получить родителей персоны."""
        if not person.famc:
            return None, None
        family = self.families.get(person.famc)
        if not family:
            return None, None
        father = self.persons.get(family.husband_id) if family.husband_id else None
        mother = self.persons.get(family.wife_id) if family.wife_id else None
        return father, mother

    def get_children(self, person: Person) -> List[Person]:
        """Получить детей персоны."""
        children = []
        for fam_id in person.fams:
            family = self.families.get(fam_id)
            if family:
                for child_id in family.children_ids:
                    child = self.persons.get(child_id)
                    if child:
                        children.append(child)
        return children

    def get_siblings(self, person: Person) -> List[Person]:
        """Получить братьев и сестёр персоны."""
        if not person.famc:
            return []
        family = self.families.get(person.famc)
        if not family:
            return []
        siblings = []
        for child_id in family.children_ids:
            if child_id != person.id:
                child = self.persons.get(child_id)
                if child:
                    siblings.append(child)
        return siblings

    def get_spouses(self, person: Person) -> List[Person]:
        """Получить супругов персоны."""
        spouses = []
        for fam_id in person.fams:
            family = self.families.get(fam_id)
            if family:
                if person.sex == 'M' and family.wife_id:
                    spouse = self.persons.get(family.wife_id)
                elif person.sex == 'F' and family.husband_id:
                    spouse = self.persons.get(family.husband_id)
                else:
                    # Неизвестный пол - пробуем оба варианта
                    spouse = None
                    if family.husband_id and family.husband_id != person.id:
                        spouse = self.persons.get(family.husband_id)
                    elif family.wife_id and family.wife_id != person.id:
                        spouse = self.persons.get(family.wife_id)
                if spouse:
                    spouses.append(spouse)
        return spouses

    def get_grandparents(self, person: Person) -> List[Person]:
        """Получить бабушек и дедушек."""
        grandparents = []
        father, mother = self.get_parents(person)
        for parent in [father, mother]:
            if parent:
                gf, gm = self.get_parents(parent)
                if gf:
                    grandparents.append(gf)
                if gm:
                    grandparents.append(gm)
        return grandparents
