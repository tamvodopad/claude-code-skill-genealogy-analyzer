#!/usr/bin/env python3
"""
Поиск родственников-тёзок для людей с именами, не соответствующими святцам.
Помогает выявить, был ли ребёнок назван в честь родственника.

Использование:
    python3 find_namesakes.py tree.ged
"""

import re
import sys
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Tuple

# Импортируем святцы и нормализацию из check_nameday
from check_nameday import SAINTS_CALENDAR, NAME_VARIANTS, normalize_name


@dataclass
class Person:
    id: str
    name: str
    given_name: str
    surname: str
    sex: str
    birth_date: Optional[date] = None
    birth_year: Optional[int] = None
    death_date: Optional[date] = None
    christening_date: Optional[date] = None
    christening_raw: str = ""
    is_julian: bool = False
    famc: Optional[str] = None  # Семья где ребёнок
    fams: List[str] = field(default_factory=list)  # Семьи где супруг
    godparents: List[str] = field(default_factory=list)  # Крёстные (ASSO)


@dataclass
class Family:
    id: str
    husband_id: Optional[str] = None
    wife_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    marriage_date: Optional[date] = None


def parse_gedcom_date(date_str: str) -> Tuple[Optional[date], bool]:
    """Парсинг даты из GEDCOM формата."""
    if not date_str:
        return None, False

    date_str = date_str.strip()
    is_julian = "@#DJULIAN@" in date_str
    clean_str = date_str.replace("@#DJULIAN@", "").strip()

    for prefix in ["ABT", "BEF", "AFT", "EST", "CAL"]:
        clean_str = clean_str.replace(prefix, "").strip()

    months = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }

    match = re.match(r'(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', clean_str)
    if match:
        day, month_str, year = match.groups()
        if month_str in months:
            try:
                return date(int(year), months[month_str], int(day)), is_julian
            except ValueError:
                pass

    # Только год
    year_match = re.search(r'(\d{4})', clean_str)
    if year_match:
        return None, is_julian  # Дата неполная

    return None, is_julian


def get_saints_for_date(d: date, window: int = 8) -> Set[str]:
    """Получение нормализованных имён святых для даты."""
    names = set()
    for offset in range(-window, window + 1):
        check_date = d + timedelta(days=offset)
        key = (check_date.month, check_date.day)
        if key in SAINTS_CALENDAR:
            m, f = SAINTS_CALENDAR[key]
            names.update(normalize_name(n) for n in m)
            names.update(normalize_name(n) for n in f)
    return names


def parse_gedcom(filepath: str) -> Tuple[Dict[str, Person], Dict[str, Family]]:
    """Полный парсинг GEDCOM файла."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    persons: Dict[str, Person] = {}
    families: Dict[str, Family] = {}

    current_type = None
    current_id = None
    current_data: Dict = {}
    in_birt = False
    in_chr = False
    in_asso = False
    asso_id = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Уровень 0 - новая запись
        if line.startswith("0 "):
            # Сохраняем предыдущую запись
            if current_type == "INDI" and current_id:
                persons[current_id] = Person(
                    id=current_id,
                    name=current_data.get('name', ''),
                    given_name=current_data.get('givn', ''),
                    surname=current_data.get('surn', ''),
                    sex=current_data.get('sex', ''),
                    birth_date=current_data.get('birth_date'),
                    birth_year=current_data.get('birth_year'),
                    death_date=current_data.get('death_date'),
                    christening_date=current_data.get('chr_date'),
                    christening_raw=current_data.get('chr_raw', ''),
                    is_julian=current_data.get('is_julian', False),
                    famc=current_data.get('famc'),
                    fams=current_data.get('fams', []),
                    godparents=current_data.get('godparents', [])
                )
            elif current_type == "FAM" and current_id:
                families[current_id] = Family(
                    id=current_id,
                    husband_id=current_data.get('husb'),
                    wife_id=current_data.get('wife'),
                    children_ids=current_data.get('children', []),
                    marriage_date=current_data.get('marr_date')
                )

            current_data = {'fams': [], 'children': [], 'godparents': []}
            in_birt = in_chr = in_asso = False

            match = re.match(r'0 (@\w+@) (\w+)', line)
            if match:
                current_id = match.group(1)
                tag = match.group(2)
                current_type = tag if tag in ('INDI', 'FAM') else None
            else:
                current_type = None
                current_id = None
            continue

        if not current_id:
            continue

        # Уровень 1
        if line.startswith("1 "):
            in_birt = in_chr = in_asso = False
            parts = line[2:].split(None, 1)
            tag = parts[0]
            value = parts[1] if len(parts) > 1 else ""

            if current_type == "INDI":
                if tag == "NAME":
                    current_data['name'] = value.replace('/', '').strip()
                elif tag == "SEX":
                    current_data['sex'] = value
                elif tag == "BIRT":
                    in_birt = True
                elif tag == "CHR":
                    in_chr = True
                elif tag == "FAMC":
                    current_data['famc'] = value
                elif tag == "FAMS":
                    current_data['fams'].append(value)
                elif tag == "ASSO":
                    in_asso = True
                    asso_id = value
            elif current_type == "FAM":
                if tag == "HUSB":
                    current_data['husb'] = value
                elif tag == "WIFE":
                    current_data['wife'] = value
                elif tag == "CHIL":
                    current_data['children'].append(value)

        # Уровень 2
        elif line.startswith("2 "):
            parts = line[2:].split(None, 1)
            tag = parts[0]
            value = parts[1] if len(parts) > 1 else ""

            if current_type == "INDI":
                if tag == "GIVN":
                    # Берём первое имя
                    given = value.strip().split()[0] if value.strip() else ""
                    current_data['givn'] = given
                elif tag == "SURN":
                    current_data['surn'] = value.strip()
                elif tag == "DATE":
                    parsed, is_julian = parse_gedcom_date(value)
                    if in_birt:
                        current_data['birth_date'] = parsed
                        if parsed:
                            current_data['birth_year'] = parsed.year
                        else:
                            year_match = re.search(r'(\d{4})', value)
                            if year_match:
                                current_data['birth_year'] = int(year_match.group(1))
                    elif in_chr:
                        current_data['chr_date'] = parsed
                        current_data['chr_raw'] = value
                        current_data['is_julian'] = is_julian
                elif tag == "RELA" and in_asso:
                    if "godp" in value.lower() or "крёстн" in value.lower() or "кресн" in value.lower():
                        if asso_id:
                            current_data['godparents'].append(asso_id)

    # Последняя запись
    if current_type == "INDI" and current_id:
        persons[current_id] = Person(
            id=current_id,
            name=current_data.get('name', ''),
            given_name=current_data.get('givn', ''),
            surname=current_data.get('surn', ''),
            sex=current_data.get('sex', ''),
            birth_date=current_data.get('birth_date'),
            birth_year=current_data.get('birth_year'),
            death_date=current_data.get('death_date'),
            christening_date=current_data.get('chr_date'),
            christening_raw=current_data.get('chr_raw', ''),
            is_julian=current_data.get('is_julian', False),
            famc=current_data.get('famc'),
            fams=current_data.get('fams', []),
            godparents=current_data.get('godparents', [])
        )
    elif current_type == "FAM" and current_id:
        families[current_id] = Family(
            id=current_id,
            husband_id=current_data.get('husb'),
            wife_id=current_data.get('wife'),
            children_ids=current_data.get('children', []),
            marriage_date=current_data.get('marr_date')
        )

    return persons, families


def find_relatives(person: Person, persons: Dict[str, Person], families: Dict[str, Family]) -> Dict[str, List[Person]]:
    """
    Найти родственников человека.
    Возвращает словарь: тип родства -> список персон
    """
    relatives: Dict[str, List[Person]] = {
        'родители': [],
        'бабушки/дедушки': [],
        'крёстные': [],
        'тёти/дяди': [],
        'старшие братья/сёстры': [],
    }

    # Родители
    if person.famc and person.famc in families:
        family = families[person.famc]
        if family.husband_id and family.husband_id in persons:
            relatives['родители'].append(persons[family.husband_id])
        if family.wife_id and family.wife_id in persons:
            relatives['родители'].append(persons[family.wife_id])

        # Бабушки/дедушки (родители родителей)
        for parent in relatives['родители']:
            if parent.famc and parent.famc in families:
                gp_family = families[parent.famc]
                if gp_family.husband_id and gp_family.husband_id in persons:
                    relatives['бабушки/дедушки'].append(persons[gp_family.husband_id])
                if gp_family.wife_id and gp_family.wife_id in persons:
                    relatives['бабушки/дедушки'].append(persons[gp_family.wife_id])

                # Тёти/дяди (братья/сёстры родителей)
                for sibling_id in gp_family.children_ids:
                    if sibling_id != parent.id and sibling_id in persons:
                        relatives['тёти/дяди'].append(persons[sibling_id])

        # Старшие братья/сёстры
        for sibling_id in family.children_ids:
            if sibling_id != person.id and sibling_id in persons:
                sibling = persons[sibling_id]
                # Проверяем что старше
                if person.birth_year and sibling.birth_year:
                    if sibling.birth_year < person.birth_year:
                        relatives['старшие братья/сёстры'].append(sibling)
                elif person.birth_date and sibling.birth_date:
                    if sibling.birth_date < person.birth_date:
                        relatives['старшие братья/сёстры'].append(sibling)

    # Крёстные
    for gp_id in person.godparents:
        if gp_id in persons:
            relatives['крёстные'].append(persons[gp_id])

    return relatives


def find_namesakes(person: Person, relatives: Dict[str, List[Person]]) -> List[Tuple[str, Person]]:
    """
    Найти тёзок среди родственников.
    Возвращает список (тип родства, персона).
    """
    namesakes = []
    person_name = normalize_name(person.given_name)

    for relation_type, rel_list in relatives.items():
        for rel in rel_list:
            rel_name = normalize_name(rel.given_name)
            if person_name == rel_name:
                namesakes.append((relation_type, rel))

    return namesakes


def analyze_namesakes(filepath: str):
    """Основной анализ."""
    print(f"Парсинг GEDCOM файла: {filepath}")
    persons, families = parse_gedcom(filepath)
    print(f"Найдено {len(persons)} персон и {len(families)} семей\n")

    # Находим людей с несовпадением со святцами
    mismatches = []
    for person in persons.values():
        if not person.christening_date or not person.given_name:
            continue

        name = normalize_name(person.given_name)
        saints = get_saints_for_date(person.christening_date)

        if name not in saints:
            mismatches.append(person)

    print("=" * 100)
    print("ИМЕНА НЕ ПО СВЯТЦАМ: ПОИСК РОДСТВЕННИКОВ-ТЁЗОК")
    print("=" * 100)
    print(f"\nВсего несовпадений со святцами: {len(mismatches)}\n")

    found_namesakes = []
    no_namesakes = []

    for person in mismatches:
        relatives = find_relatives(person, persons, families)
        namesakes = find_namesakes(person, relatives)

        if namesakes:
            found_namesakes.append((person, namesakes))
        else:
            no_namesakes.append(person)

    # Выводим найденных тёзок
    print("=" * 100)
    print(f"✅ НАЙДЕНЫ ПОТЕНЦИАЛЬНЫЕ ТЁЗКИ-РОДСТВЕННИКИ: {len(found_namesakes)}")
    print("=" * 100)

    for person, namesakes in found_namesakes:
        chr_date = person.christening_date.strftime('%d.%m.%Y') if person.christening_date else "?"
        julian_mark = " (ст.ст.)" if person.is_julian else ""

        print(f"\n👤 {person.name}")
        print(f"   📅 Крещение: {chr_date}{julian_mark}")
        print(f"   📛 Имя: {person.given_name}")
        print(f"   🔗 Возможно назван(а) в честь:")

        for relation_type, namesake in namesakes:
            ns_birth = ""
            if namesake.birth_year:
                ns_birth = f", р. {namesake.birth_year}"
            elif namesake.birth_date:
                ns_birth = f", р. {namesake.birth_date.strftime('%d.%m.%Y')}"

            ns_death = ""
            if namesake.death_date:
                ns_death = f", † {namesake.death_date.strftime('%d.%m.%Y')}"

            print(f"      → {namesake.name} ({relation_type}{ns_birth}{ns_death})")

    # Выводим без тёзок
    print("\n" + "=" * 100)
    print(f"❓ ТЁЗКИ НЕ НАЙДЕНЫ: {len(no_namesakes)}")
    print("=" * 100)

    for person in no_namesakes:
        chr_date = person.christening_date.strftime('%d.%m.%Y') if person.christening_date else "?"
        julian_mark = " (ст.ст.)" if person.is_julian else ""

        print(f"\n👤 {person.name}")
        print(f"   📅 Крещение: {chr_date}{julian_mark}")
        print(f"   📛 Имя: {person.given_name}")

    # Статистика
    print("\n" + "=" * 100)
    print("СТАТИСТИКА")
    print("=" * 100)
    print(f"Всего имён не по святцам: {len(mismatches)}")
    print(f"Найдены тёзки-родственники: {len(found_namesakes)} ({100*len(found_namesakes)//len(mismatches) if mismatches else 0}%)")
    print(f"Тёзки не найдены: {len(no_namesakes)} ({100*len(no_namesakes)//len(mismatches) if mismatches else 0}%)")


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 find_namesakes.py tree.ged")
        sys.exit(1)

    analyze_namesakes(sys.argv[1])


if __name__ == '__main__':
    main()
