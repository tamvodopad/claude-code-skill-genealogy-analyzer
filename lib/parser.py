"""
Парсер GEDCOM файлов.
"""

import re
from datetime import date
from typing import Optional, Tuple, Dict
from .models import Person, Family, GedcomData


MONTHS = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}


def parse_date(date_str: str) -> Tuple[Optional[date], Optional[int], bool]:
    """
    Парсинг даты из GEDCOM формата.
    Возвращает: (полная_дата, год, is_julian)
    """
    if not date_str:
        return None, None, False

    date_str = date_str.strip()
    is_julian = "@#DJULIAN@" in date_str
    clean_str = date_str.replace("@#DJULIAN@", "").strip()

    # Убираем модификаторы
    for prefix in ["ABT", "BEF", "AFT", "EST", "CAL", "FROM", "TO", "BET", "AND"]:
        clean_str = re.sub(rf'\b{prefix}\b', '', clean_str).strip()

    # Полная дата: "15 MAY 1893"
    match = re.match(r'(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', clean_str)
    if match:
        day, month_str, year = match.groups()
        if month_str in MONTHS:
            try:
                return date(int(year), MONTHS[month_str], int(day)), int(year), is_julian
            except ValueError:
                pass

    # Месяц и год: "MAY 1893"
    match = re.match(r'([A-Z]{3})\s+(\d{4})', clean_str)
    if match:
        month_str, year = match.groups()
        if month_str in MONTHS:
            return None, int(year), is_julian

    # Только год: "1893"
    match = re.search(r'(\d{4})', clean_str)
    if match:
        return None, int(match.group(1)), is_julian

    return None, None, is_julian


def extract_patronymic(full_name: str) -> str:
    """
    Извлечение отчества из полного имени.
    Например: "Константин Александрович" -> "Александрович"
    """
    # Удаляем фамилию (в слэшах) если есть
    name = re.sub(r'/[^/]*/', '', full_name).strip()
    parts = name.split()

    if len(parts) >= 2:
        # Отчество обычно второе слово, заканчивается на -вич/-вна/-ич/-ична
        for part in parts[1:]:
            if re.search(r'(вич|вна|ич|ична|евич|евна|ович|овна)$', part, re.IGNORECASE):
                return part
    return ""


def extract_given_name(full_name: str) -> str:
    """
    Извлечение имени (без фамилии и отчества).
    """
    # Удаляем фамилию (в слэшах)
    name = re.sub(r'/[^/]*/', '', full_name).strip()
    parts = name.split()
    return parts[0] if parts else ""


def parse_gedcom(filepath: str) -> GedcomData:
    """
    Парсинг GEDCOM файла.
    Возвращает объект GedcomData со всеми персонами и семьями.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = GedcomData()

    current_type = None
    current_id = None
    current_data: Dict = {}

    # Контекст для вложенных тегов
    in_birt = False
    in_deat = False
    in_marr = False
    in_chr = False
    in_resi = False
    in_asso = False
    asso_id = None

    for line in lines:
        line = line.rstrip('\n\r')
        if not line.strip():
            continue

        # Парсим уровень, xref, тег и значение
        match = re.match(r'^(\d+)\s+(@[^@]+@)?\s*(\w+)?\s*(.*)?$', line)
        if not match:
            continue

        level = int(match.group(1))
        xref = match.group(2)
        tag = match.group(3) or ""
        value = match.group(4) or ""

        # Уровень 0 - новая запись
        if level == 0:
            # Сохраняем предыдущую запись
            if current_type == "INDI" and current_id:
                person = Person(
                    id=current_id,
                    name=current_data.get('name', ''),
                    given_name=current_data.get('givn', '') or extract_given_name(current_data.get('name', '')),
                    surname=current_data.get('surn', ''),
                    patronymic=current_data.get('patronymic', '') or extract_patronymic(current_data.get('name', '')),
                    sex=current_data.get('sex', ''),
                    birth_date=current_data.get('birth_date'),
                    birth_year=current_data.get('birth_year'),
                    birth_place=current_data.get('birth_place', ''),
                    birth_is_julian=current_data.get('birth_is_julian', False),
                    death_date=current_data.get('death_date'),
                    death_year=current_data.get('death_year'),
                    death_place=current_data.get('death_place', ''),
                    death_cause=current_data.get('death_cause', ''),
                    death_is_julian=current_data.get('death_is_julian', False),
                    christening_date=current_data.get('chr_date'),
                    christening_is_julian=current_data.get('chr_is_julian', False),
                    famc=current_data.get('famc'),
                    fams=current_data.get('fams', []),
                    occupation=current_data.get('occu', ''),
                    residence=current_data.get('residence', []),
                    godparents=current_data.get('godparents', []),
                    notes=current_data.get('notes', [])
                )
                data.persons[current_id] = person

            elif current_type == "FAM" and current_id:
                family = Family(
                    id=current_id,
                    husband_id=current_data.get('husb'),
                    wife_id=current_data.get('wife'),
                    children_ids=current_data.get('children', []),
                    marriage_date=current_data.get('marr_date'),
                    marriage_year=current_data.get('marr_year'),
                    marriage_place=current_data.get('marr_place', ''),
                    marriage_is_julian=current_data.get('marr_is_julian', False),
                    divorce_date=current_data.get('div_date')
                )
                data.families[current_id] = family

            # Сбрасываем для новой записи
            current_data = {'fams': [], 'children': [], 'residence': [], 'godparents': [], 'notes': []}
            in_birt = in_deat = in_marr = in_chr = in_resi = in_asso = False

            if tag == "INDI":
                current_type = "INDI"
                current_id = xref
            elif tag == "FAM":
                current_type = "FAM"
                current_id = xref
            else:
                current_type = None
                current_id = None
            continue

        if not current_id:
            continue

        # Уровень 1 - основные теги
        if level == 1:
            in_birt = in_deat = in_marr = in_chr = in_resi = in_asso = False

            if current_type == "INDI":
                if tag == "NAME":
                    current_data['name'] = value.replace('/', '').strip()
                elif tag == "SEX":
                    current_data['sex'] = value.strip()
                elif tag == "BIRT":
                    in_birt = True
                elif tag == "DEAT":
                    in_deat = True
                elif tag == "CHR":
                    in_chr = True
                elif tag == "RESI":
                    in_resi = True
                    current_data['current_resi'] = {}
                elif tag == "FAMC":
                    current_data['famc'] = value.strip()
                elif tag == "FAMS":
                    current_data['fams'].append(value.strip())
                elif tag == "OCCU":
                    current_data['occu'] = value.strip()
                elif tag == "NOTE":
                    current_data['notes'].append(value.strip())
                elif tag == "ASSO":
                    in_asso = True
                    asso_id = value.strip()

            elif current_type == "FAM":
                if tag == "HUSB":
                    current_data['husb'] = value.strip()
                elif tag == "WIFE":
                    current_data['wife'] = value.strip()
                elif tag == "CHIL":
                    current_data['children'].append(value.strip())
                elif tag == "MARR":
                    in_marr = True
                elif tag == "DIV":
                    pass  # TODO: обработать развод

        # Уровень 2 - вложенные данные
        elif level == 2:
            if current_type == "INDI":
                if tag == "GIVN":
                    # Берём только первое имя
                    given = value.strip().split()[0] if value.strip() else ""
                    current_data['givn'] = given
                elif tag == "SURN":
                    current_data['surn'] = value.strip()
                elif tag == "DATE":
                    parsed_date, year, is_julian = parse_date(value)
                    if in_birt:
                        current_data['birth_date'] = parsed_date
                        current_data['birth_year'] = year
                        current_data['birth_is_julian'] = is_julian
                    elif in_deat:
                        current_data['death_date'] = parsed_date
                        current_data['death_year'] = year
                        current_data['death_is_julian'] = is_julian
                    elif in_chr:
                        current_data['chr_date'] = parsed_date
                        current_data['chr_is_julian'] = is_julian
                    elif in_resi:
                        current_data['current_resi']['date'] = value.strip()
                elif tag == "PLAC":
                    if in_birt:
                        current_data['birth_place'] = value.strip()
                    elif in_deat:
                        current_data['death_place'] = value.strip()
                    elif in_resi:
                        current_data['current_resi']['place'] = value.strip()
                elif tag == "CAUS" and in_deat:
                    current_data['death_cause'] = value.strip()
                elif tag == "RELA" and in_asso:
                    if "godp" in value.lower() or "крёстн" in value.lower() or "кресн" in value.lower():
                        if asso_id:
                            current_data['godparents'].append(asso_id)

            elif current_type == "FAM":
                if tag == "DATE" and in_marr:
                    parsed_date, year, is_julian = parse_date(value)
                    current_data['marr_date'] = parsed_date
                    current_data['marr_year'] = year
                    current_data['marr_is_julian'] = is_julian
                elif tag == "PLAC" and in_marr:
                    current_data['marr_place'] = value.strip()

        # Уровень 3+ - координаты и т.д.
        elif level == 3:
            if tag == "MAP" or in_resi:
                pass  # Пропускаем MAP, обрабатываем LATI/LONG на уровне 4

        elif level == 4:
            if in_resi and current_data.get('current_resi') is not None:
                if tag == "LATI":
                    current_data['current_resi']['lat'] = value.strip()
                elif tag == "LONG":
                    current_data['current_resi']['lon'] = value.strip()

    # Сохраняем последнюю запись
    if current_type == "INDI" and current_id:
        person = Person(
            id=current_id,
            name=current_data.get('name', ''),
            given_name=current_data.get('givn', '') or extract_given_name(current_data.get('name', '')),
            surname=current_data.get('surn', ''),
            patronymic=current_data.get('patronymic', '') or extract_patronymic(current_data.get('name', '')),
            sex=current_data.get('sex', ''),
            birth_date=current_data.get('birth_date'),
            birth_year=current_data.get('birth_year'),
            birth_place=current_data.get('birth_place', ''),
            birth_is_julian=current_data.get('birth_is_julian', False),
            death_date=current_data.get('death_date'),
            death_year=current_data.get('death_year'),
            death_place=current_data.get('death_place', ''),
            death_cause=current_data.get('death_cause', ''),
            death_is_julian=current_data.get('death_is_julian', False),
            christening_date=current_data.get('chr_date'),
            christening_is_julian=current_data.get('chr_is_julian', False),
            famc=current_data.get('famc'),
            fams=current_data.get('fams', []),
            occupation=current_data.get('occu', ''),
            residence=current_data.get('residence', []),
            godparents=current_data.get('godparents', []),
            notes=current_data.get('notes', [])
        )
        data.persons[current_id] = person

    elif current_type == "FAM" and current_id:
        family = Family(
            id=current_id,
            husband_id=current_data.get('husb'),
            wife_id=current_data.get('wife'),
            children_ids=current_data.get('children', []),
            marriage_date=current_data.get('marr_date'),
            marriage_year=current_data.get('marr_year'),
            marriage_place=current_data.get('marr_place', ''),
            marriage_is_julian=current_data.get('marr_is_julian', False),
            divorce_date=current_data.get('div_date')
        )
        data.families[current_id] = family

    return data
