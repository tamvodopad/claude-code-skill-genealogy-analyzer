#!/usr/bin/env python3
"""
Анализатор браков в GEDCOM файлах.
Ищет нетипичные даты венчаний по православным традициям (до 1917).

Использование:
    python3 analyze_marriages.py tree.ged [--before YEAR] [--output FILE]

Примеры:
    python3 analyze_marriages.py tree.ged
    python3 analyze_marriages.py tree.ged --before 1930
    python3 analyze_marriages.py tree.ged --before 1920 --output report.txt
"""

import re
import sys
import argparse
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict


@dataclass
class Person:
    id: str
    name: str
    birth_date: Optional[date] = None
    birth_year: Optional[int] = None


@dataclass
class Marriage:
    family_id: str
    husband: Optional[Person]
    wife: Optional[Person]
    date: Optional[date]
    date_raw: str
    place: str
    is_julian: bool
    children_ids: List[str]


@dataclass
class Child:
    id: str
    name: str
    birth_date: Optional[date]
    birth_year: Optional[int]
    death_date: Optional[date]
    death_cause: str


def orthodox_easter_julian(year: int) -> date:
    """
    Расчёт православной Пасхи по алгоритму Гаусса.
    Возвращает дату по юлианскому календарю.
    """
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    return date(year, month, day)


def julian_to_gregorian(julian_date: date) -> date:
    """Конвертация юлианской даты в григорианскую."""
    if julian_date.year < 1900:
        delta = 12
    else:
        delta = 13
    return julian_date + timedelta(days=delta)


def get_wedding_windows_julian(year: int) -> List[Tuple[date, date, str]]:
    """
    Возвращает разрешённые периоды для венчания (юлианский календарь).
    """
    easter = orthodox_easter_julian(year)

    # Зимний свадебник: 7 января — за неделю до Масленицы
    winter_start = date(year, 1, 7)  # Крещение
    maslenitsa_start = easter - timedelta(days=56)  # Начало Масленицы
    winter_end = maslenitsa_start - timedelta(days=1)

    # Если зимний период начинается в прошлом году
    if winter_end < winter_start:
        prev_easter = orthodox_easter_julian(year - 1)
        prev_winter_start = date(year - 1, 1, 7)
        prev_maslenitsa = prev_easter - timedelta(days=56)
        # Используем период этого года
        winter_start = date(year, 1, 7)
        winter_end = maslenitsa_start - timedelta(days=1)

    # Весенний свадебник: Красная горка — Троица
    krasnaya_gorka = easter + timedelta(days=7)
    trinity = easter + timedelta(days=49)

    # Осенний свадебник: Покров — Филиппово заговенье
    pokrov = date(year, 10, 1)
    filippov = date(year, 11, 14)

    return [
        (winter_start, winter_end, "Зимний свадебник (Крещение - Масленица)"),
        (krasnaya_gorka, trinity, "Весенний свадебник (Красная горка - Троица)"),
        (pokrov, filippov, "Осенний свадебник (Покров - Филиппово заговенье)"),
    ]


def get_forbidden_periods_julian(year: int) -> List[Tuple[date, date, str]]:
    """
    Возвращает запретные периоды для венчания (юлианский календарь).
    """
    easter = orthodox_easter_julian(year)
    trinity = easter + timedelta(days=49)

    return [
        (easter - timedelta(days=48), easter - timedelta(days=1), "Великий пост"),
        (trinity + timedelta(days=1), date(year, 6, 28), "Петров пост"),
        (date(year, 8, 1), date(year, 8, 14), "Успенский пост"),
        (date(year, 11, 15), date(year, 12, 24), "Рождественский пост"),
    ]


def parse_gedcom_date(date_str: str) -> Tuple[Optional[date], bool, str]:
    """
    Парсинг даты из GEDCOM формата.
    Возвращает: (date, is_julian, raw_string)
    """
    if not date_str:
        return None, False, ""

    date_str = date_str.strip()
    is_julian = "@#DJULIAN@" in date_str
    clean_str = date_str.replace("@#DJULIAN@", "").strip()

    # Убираем модификаторы
    for prefix in ["ABT", "BEF", "AFT", "EST", "CAL"]:
        clean_str = clean_str.replace(prefix, "").strip()

    months = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }

    # Полная дата: "15 MAY 1893"
    match = re.match(r'(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', clean_str)
    if match:
        day, month_str, year = match.groups()
        if month_str in months:
            try:
                return date(int(year), months[month_str], int(day)), is_julian, date_str
            except ValueError:
                pass

    # Только месяц и год: "MAY 1893"
    match = re.match(r'([A-Z]{3})\s+(\d{4})', clean_str)
    if match:
        month_str, year = match.groups()
        if month_str in months:
            try:
                return date(int(year), months[month_str], 1), is_julian, date_str
            except ValueError:
                pass

    # Только год: "1893"
    match = re.match(r'(\d{4})', clean_str)
    if match:
        year = match.group(1)
        return None, is_julian, date_str  # Год есть, но полной даты нет

    return None, is_julian, date_str


def parse_gedcom(filepath: str) -> Tuple[Dict[str, Person], List[Marriage]]:
    """
    Парсинг GEDCOM файла.
    Возвращает словарь персон и список браков.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    persons = {}
    marriages = []

    current_record = None
    current_id = None
    current_data = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Парсинг уровня и тега
        match = re.match(r'^(\d+)\s+(@\w+@)?\s*(\w+)?\s*(.*)?$', line)
        if not match:
            i += 1
            continue

        level = int(match.group(1))
        xref = match.group(2)
        tag = match.group(3) or ""
        value = match.group(4) or ""

        # Новая запись верхнего уровня
        if level == 0:
            # Сохраняем предыдущую запись
            if current_record == 'INDI' and current_id:
                persons[current_id] = Person(
                    id=current_id,
                    name=current_data.get('name', 'Unknown'),
                    birth_date=current_data.get('birth_date'),
                    birth_year=current_data.get('birth_year')
                )
            elif current_record == 'FAM' and current_id:
                marriages.append(Marriage(
                    family_id=current_id,
                    husband=None,  # Заполним позже
                    wife=None,
                    date=current_data.get('marr_date'),
                    date_raw=current_data.get('marr_date_raw', ''),
                    place=current_data.get('marr_place', ''),
                    is_julian=current_data.get('is_julian', False),
                    children_ids=current_data.get('children', [])
                ))

            # Начинаем новую запись
            current_data = {}
            if tag == 'INDI':
                current_record = 'INDI'
                current_id = xref
            elif tag == 'FAM':
                current_record = 'FAM'
                current_id = xref
                current_data['children'] = []
                current_data['husb_id'] = None
                current_data['wife_id'] = None
            else:
                current_record = None
                current_id = None

        # Обработка данных записи
        elif current_record == 'INDI':
            if tag == 'NAME':
                current_data['name'] = value.replace('/', '').strip()
            elif tag == 'BIRT':
                # Следующая строка может быть DATE
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith('2 DATE'):
                        date_val = next_line[7:].strip()
                        parsed_date, is_julian, raw = parse_gedcom_date(date_val)
                        current_data['birth_date'] = parsed_date
                        if parsed_date:
                            current_data['birth_year'] = parsed_date.year
                        else:
                            # Попробовать извлечь год
                            year_match = re.search(r'(\d{4})', date_val)
                            if year_match:
                                current_data['birth_year'] = int(year_match.group(1))

        elif current_record == 'FAM':
            if tag == 'HUSB':
                current_data['husb_id'] = value
            elif tag == 'WIFE':
                current_data['wife_id'] = value
            elif tag == 'CHIL':
                current_data['children'].append(value)
            elif tag == 'MARR':
                # Следующая строка может быть DATE
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith('2 DATE'):
                        date_val = next_line[7:].strip()
                        parsed_date, is_julian, raw = parse_gedcom_date(date_val)
                        current_data['marr_date'] = parsed_date
                        current_data['marr_date_raw'] = raw
                        current_data['is_julian'] = is_julian
                # Ищем PLAC
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith('2 '):
                    if lines[j].strip().startswith('2 PLAC'):
                        current_data['marr_place'] = lines[j].strip()[7:].strip()
                        break
                    j += 1

        i += 1

    # Сохраняем последнюю запись
    if current_record == 'INDI' and current_id:
        persons[current_id] = Person(
            id=current_id,
            name=current_data.get('name', 'Unknown'),
            birth_date=current_data.get('birth_date'),
            birth_year=current_data.get('birth_year')
        )
    elif current_record == 'FAM' and current_id:
        marriages.append(Marriage(
            family_id=current_id,
            husband=None,
            wife=None,
            date=current_data.get('marr_date'),
            date_raw=current_data.get('marr_date_raw', ''),
            place=current_data.get('marr_place', ''),
            is_julian=current_data.get('is_julian', False),
            children_ids=current_data.get('children', [])
        ))

    # Связываем персон с браками
    # Перечитываем файл для связей
    current_fam_id = None
    husb_id = None
    wife_id = None

    for line in lines:
        line = line.strip()
        if line.startswith('0 @F'):
            if current_fam_id and (husb_id or wife_id):
                for m in marriages:
                    if m.family_id == current_fam_id:
                        if husb_id and husb_id in persons:
                            m.husband = persons[husb_id]
                        if wife_id and wife_id in persons:
                            m.wife = persons[wife_id]
            match = re.match(r'0 (@F\d+@)', line)
            if match:
                current_fam_id = match.group(1)
                husb_id = None
                wife_id = None
        elif line.startswith('1 HUSB'):
            match = re.search(r'(@I\d+@)', line)
            if match:
                husb_id = match.group(1)
        elif line.startswith('1 WIFE'):
            match = re.search(r'(@I\d+@)', line)
            if match:
                wife_id = match.group(1)

    # Последняя семья
    if current_fam_id and (husb_id or wife_id):
        for m in marriages:
            if m.family_id == current_fam_id:
                if husb_id and husb_id in persons:
                    m.husband = persons[husb_id]
                if wife_id and wife_id in persons:
                    m.wife = persons[wife_id]

    return persons, marriages


def classify_marriage_date(marriage_date: date, is_julian: bool) -> Tuple[str, str]:
    """
    Классифицирует дату брака.
    Возвращает: (категория, описание)
    Категории: 'typical', 'atypical', 'forbidden'
    """
    year = marriage_date.year

    # Проверяем запретные периоды
    forbidden = get_forbidden_periods_julian(year)
    for start, end, name in forbidden:
        if start <= marriage_date <= end:
            return 'forbidden', f"Венчание в {name} ({start.strftime('%d.%m')} - {end.strftime('%d.%m')})"

    # Проверяем разрешённые периоды
    windows = get_wedding_windows_julian(year)
    for start, end, name in windows:
        if start <= marriage_date <= end:
            return 'typical', name

    # Нетипичный период
    month = marriage_date.month
    if month in [6, 7, 8]:
        return 'atypical', "Летние месяцы - страда, венчания редки"
    elif month == 9:
        return 'atypical', "Сентябрь - уборка урожая, венчания редки"
    else:
        return 'atypical', "Вне традиционных свадебных периодов"


def analyze_marriages(filepath: str, before_year: int = 1930) -> None:
    """
    Основная функция анализа.
    """
    print(f"Парсинг GEDCOM файла...")
    persons, marriages = parse_gedcom(filepath)
    print(f"Найдено {len(persons)} персон и {len(marriages)} записей о браках\n")

    # Фильтруем браки с точными датами до указанного года
    filtered = []
    for m in marriages:
        if m.date and m.date.year < before_year:
            filtered.append(m)

    print(f"Браков до {before_year} с точными датами: {len(filtered)}\n")

    if not filtered:
        print("Нет браков для анализа.")
        return

    # Классифицируем
    typical = []
    atypical = []
    forbidden = []

    for m in filtered:
        category, description = classify_marriage_date(m.date, m.is_julian)
        if category == 'typical':
            typical.append((m, description))
        elif category == 'atypical':
            atypical.append((m, description))
        else:
            forbidden.append((m, description))

    # Вывод результатов
    print("=" * 100)
    print("АНАЛИЗ ДАТ БРАКОВ ДО", before_year, "ГОДА")
    print("=" * 100)

    # Запретные периоды
    if forbidden:
        print("\n" + "=" * 100)
        print("❌ БРАКИ В ЗАПРЕТНЫЕ ПЕРИОДЫ (требуют особого внимания)")
        print("=" * 100)
        for m, desc in forbidden:
            easter = orthodox_easter_julian(m.date.year)
            greg_date = julian_to_gregorian(m.date) if m.is_julian else m.date

            print(f"\n📅 {m.date.strftime('%d.%m.%Y')} ст.ст. ({greg_date.strftime('%d.%m.%Y')} н.ст.)")
            husband_name = m.husband.name if m.husband else "?"
            wife_name = m.wife.name if m.wife else "?"
            print(f"   👫 {husband_name} + {wife_name}")
            if m.place:
                print(f"   📍 {m.place}")
            print(f"   ❌ {desc}")

    # Нетипичные даты
    if atypical:
        print("\n" + "=" * 100)
        print("⚠️ НЕТИПИЧНЫЕ ДАТЫ БРАКОВ (не в традиционные свадебные периоды)")
        print("=" * 100)
        for m, desc in atypical:
            easter = orthodox_easter_julian(m.date.year)
            greg_date = julian_to_gregorian(m.date) if m.is_julian else m.date

            print(f"\n📅 {m.date.strftime('%d.%m.%Y')} ст.ст. ({greg_date.strftime('%d.%m.%Y')} н.ст.)")
            husband_name = m.husband.name if m.husband else "?"
            wife_name = m.wife.name if m.wife else "?"
            print(f"   👫 {husband_name} + {wife_name}")
            if m.place:
                print(f"   📍 {m.place}")
            print(f"   ⚠️  {desc}")
            print(f"   🐣 Пасха {m.date.year}: {easter.strftime('%d.%m')} ст.ст. ({julian_to_gregorian(easter).strftime('%d.%m')} н.ст.)")

    # Типичные даты
    if typical:
        print("\n" + "=" * 100)
        print("✅ ТИПИЧНЫЕ ДАТЫ БРАКОВ (в традиционные свадебные периоды)")
        print("=" * 100)
        for m, desc in typical:
            greg_date = julian_to_gregorian(m.date) if m.is_julian else m.date

            print(f"\n✅ {m.date.strftime('%d.%m.%Y')} ст.ст. ({greg_date.strftime('%d.%m.%Y')} н.ст.)")
            husband_name = m.husband.name if m.husband else "?"
            wife_name = m.wife.name if m.wife else "?"
            print(f"   👫 {husband_name} + {wife_name}")
            if m.place:
                print(f"   📍 {m.place}")
            print(f"   {desc}")

    # Статистика
    total = len(filtered)
    print("\n" + "=" * 100)
    print("СТАТИСТИКА")
    print("=" * 100)
    print(f"Всего браков до {before_year} с точными датами: {total}")
    print(f"Типичные (в традиционные периоды):    {len(typical)} ({len(typical)*100//total}%)")
    print(f"Нетипичные:                            {len(atypical)} ({len(atypical)*100//total}%)")
    print(f"В запретные периоды:                   {len(forbidden)} ({len(forbidden)*100//total}%)")


def main():
    parser = argparse.ArgumentParser(
        description='Анализ дат браков в GEDCOM файле по православным традициям'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, default=1930,
                        help='Анализировать браки до указанного года (по умолчанию: 1930)')
    parser.add_argument('--output', '-o', help='Сохранить результат в файл')

    args = parser.parse_args()

    if args.output:
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            analyze_marriages(args.gedcom_file, args.before)

        output = f.getvalue()
        print(output)

        with open(args.output, 'w', encoding='utf-8') as outfile:
            outfile.write(output)
        print(f"\nРезультат сохранён в: {args.output}")
    else:
        analyze_marriages(args.gedcom_file, args.before)


if __name__ == '__main__':
    main()
