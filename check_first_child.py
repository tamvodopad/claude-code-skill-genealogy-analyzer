#!/usr/bin/env python3
"""
Проверка даты рождения первого ребёнка относительно даты брака.
Выявляет возможную добрачную беременность.

Использование:
    python3 check_first_child.py tree.ged [--threshold DAYS]

Примеры:
    python3 check_first_child.py tree.ged
    python3 check_first_child.py tree.ged --threshold 200
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
    death_date: Optional[date] = None
    death_cause: str = ""


@dataclass
class Family:
    id: str
    husband_id: Optional[str]
    wife_id: Optional[str]
    marriage_date: Optional[date]
    marriage_raw: str
    children_ids: List[str]
    is_julian: bool


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

    # Полная дата
    match = re.match(r'(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', clean_str)
    if match:
        day, month_str, year = match.groups()
        if month_str in months:
            try:
                return date(int(year), months[month_str], int(day)), is_julian
            except ValueError:
                pass

    return None, is_julian


def parse_gedcom(filepath: str) -> Tuple[Dict[str, Person], List[Family]]:
    """Парсинг GEDCOM файла."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    persons = {}
    families = []

    current_type = None
    current_id = None
    current_data = {}
    in_birt = False
    in_deat = False
    in_marr = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.match(r'^(\d+)\s+(@\w+@)?\s*(\w+)?\s*(.*)?$', line)
        if not match:
            continue

        level = int(match.group(1))
        xref = match.group(2)
        tag = match.group(3) or ""
        value = match.group(4) or ""

        if level == 0:
            # Сохраняем предыдущую запись
            if current_type == 'INDI' and current_id:
                persons[current_id] = Person(
                    id=current_id,
                    name=current_data.get('name', '?'),
                    birth_date=current_data.get('birth_date'),
                    birth_year=current_data.get('birth_year'),
                    death_date=current_data.get('death_date'),
                    death_cause=current_data.get('death_cause', '')
                )
            elif current_type == 'FAM' and current_id:
                families.append(Family(
                    id=current_id,
                    husband_id=current_data.get('husb'),
                    wife_id=current_data.get('wife'),
                    marriage_date=current_data.get('marr_date'),
                    marriage_raw=current_data.get('marr_raw', ''),
                    children_ids=current_data.get('children', []),
                    is_julian=current_data.get('is_julian', False)
                ))

            current_data = {'children': []}
            in_birt = in_deat = in_marr = False

            if tag == 'INDI':
                current_type = 'INDI'
                current_id = xref
            elif tag == 'FAM':
                current_type = 'FAM'
                current_id = xref
            else:
                current_type = None
                current_id = None

        elif level == 1:
            in_birt = in_deat = in_marr = False
            if current_type == 'INDI':
                if tag == 'NAME':
                    current_data['name'] = value.replace('/', '').strip()
                elif tag == 'BIRT':
                    in_birt = True
                elif tag == 'DEAT':
                    in_deat = True
            elif current_type == 'FAM':
                if tag == 'HUSB':
                    current_data['husb'] = value
                elif tag == 'WIFE':
                    current_data['wife'] = value
                elif tag == 'CHIL':
                    current_data['children'].append(value)
                elif tag == 'MARR':
                    in_marr = True

        elif level == 2:
            if tag == 'DATE':
                parsed, is_julian = parse_gedcom_date(value)
                if in_birt and current_type == 'INDI':
                    current_data['birth_date'] = parsed
                    if parsed:
                        current_data['birth_year'] = parsed.year
                    else:
                        year_match = re.search(r'(\d{4})', value)
                        if year_match:
                            current_data['birth_year'] = int(year_match.group(1))
                elif in_deat and current_type == 'INDI':
                    current_data['death_date'] = parsed
                elif in_marr and current_type == 'FAM':
                    current_data['marr_date'] = parsed
                    current_data['marr_raw'] = value
                    current_data['is_julian'] = is_julian
            elif tag == 'CAUS' and in_deat:
                current_data['death_cause'] = value

    # Последняя запись
    if current_type == 'INDI' and current_id:
        persons[current_id] = Person(
            id=current_id,
            name=current_data.get('name', '?'),
            birth_date=current_data.get('birth_date'),
            birth_year=current_data.get('birth_year'),
            death_date=current_data.get('death_date'),
            death_cause=current_data.get('death_cause', '')
        )
    elif current_type == 'FAM' and current_id:
        families.append(Family(
            id=current_id,
            husband_id=current_data.get('husb'),
            wife_id=current_data.get('wife'),
            marriage_date=current_data.get('marr_date'),
            marriage_raw=current_data.get('marr_raw', ''),
            children_ids=current_data.get('children', []),
            is_julian=current_data.get('is_julian', False)
        ))

    return persons, families


def analyze_first_children(filepath: str, threshold_days: int = 260):
    """
    Анализ дат рождения первых детей.

    threshold_days: порог в днях для подозрительных случаев (по умолчанию 260 - нормальная беременность)
    """
    print(f"Парсинг GEDCOM файла...")
    persons, families = parse_gedcom(filepath)
    print(f"Найдено {len(persons)} персон и {len(families)} семей\n")

    suspicious = []
    very_suspicious = []
    impossible = []

    for family in families:
        if not family.marriage_date or not family.children_ids:
            continue

        # Находим детей с датами рождения
        children_with_dates = []
        for child_id in family.children_ids:
            if child_id in persons:
                child = persons[child_id]
                if child.birth_date:
                    children_with_dates.append(child)

        if not children_with_dates:
            continue

        # Сортируем по дате рождения
        children_with_dates.sort(key=lambda c: c.birth_date)
        first_child = children_with_dates[0]

        # Вычисляем разницу
        days_diff = (first_child.birth_date - family.marriage_date).days

        husband_name = persons[family.husband_id].name if family.husband_id and family.husband_id in persons else "?"
        wife_name = persons[family.wife_id].name if family.wife_id and family.wife_id in persons else "?"

        record = {
            'family': family,
            'husband': husband_name,
            'wife': wife_name,
            'marriage_date': family.marriage_date,
            'first_child': first_child,
            'days_diff': days_diff
        }

        if days_diff < 0:
            # Ребёнок ДО свадьбы!
            impossible.append(record)
        elif days_diff < 100:
            # Явно добрачная беременность
            very_suspicious.append(record)
        elif days_diff < threshold_days:
            # Подозрительно рано
            suspicious.append(record)

    # Вывод результатов
    print("=" * 100)
    print("АНАЛИЗ ДАТ РОЖДЕНИЯ ПЕРВЫХ ДЕТЕЙ")
    print("=" * 100)

    if impossible:
        print("\n" + "=" * 100)
        print("❌ КРИТИЧЕСКИЕ АНОМАЛИИ: Ребёнок родился ДО свадьбы родителей")
        print("=" * 100)
        for r in impossible:
            print(f"\n❌ {r['husband']} + {r['wife']}")
            print(f"   📅 Свадьба: {r['marriage_date'].strftime('%d.%m.%Y')}")
            print(f"   👶 Первый ребёнок: {r['first_child'].name}")
            print(f"   📅 Рождение: {r['first_child'].birth_date.strftime('%d.%m.%Y')}")
            print(f"   ⚠️  Разница: {r['days_diff']} дней (ДО свадьбы!)")
            print(f"   💡 Возможно: ошибка данных, приёмный ребёнок, ребёнок от другого отца")

    if very_suspicious:
        print("\n" + "=" * 100)
        print("⚠️ ЯВНАЯ ДОБРАЧНАЯ БЕРЕМЕННОСТЬ: Ребёнок родился < 100 дней после свадьбы")
        print("=" * 100)
        for r in very_suspicious:
            print(f"\n⚠️ {r['husband']} + {r['wife']}")
            print(f"   📅 Свадьба: {r['marriage_date'].strftime('%d.%m.%Y')}")
            print(f"   👶 Первый ребёнок: {r['first_child'].name}")
            print(f"   📅 Рождение: {r['first_child'].birth_date.strftime('%d.%m.%Y')}")
            print(f"   ⚠️  Разница: {r['days_diff']} дней")
            # Примерная дата зачатия
            conception = r['first_child'].birth_date - timedelta(days=270)
            print(f"   💡 Примерная дата зачатия: {conception.strftime('%d.%m.%Y')} (до свадьбы)")

    if suspicious:
        print("\n" + "=" * 100)
        print(f"🔍 ПОДОЗРИТЕЛЬНЫЕ СЛУЧАИ: Ребёнок родился < {threshold_days} дней после свадьбы")
        print("=" * 100)
        for r in suspicious:
            print(f"\n🔍 {r['husband']} + {r['wife']}")
            print(f"   📅 Свадьба: {r['marriage_date'].strftime('%d.%m.%Y')}")
            print(f"   👶 Первый ребёнок: {r['first_child'].name}")
            print(f"   📅 Рождение: {r['first_child'].birth_date.strftime('%d.%m.%Y')}")
            print(f"   🔍 Разница: {r['days_diff']} дней")

    # Статистика
    total_analyzed = len(impossible) + len(very_suspicious) + len(suspicious)
    total_families_with_data = len([f for f in families if f.marriage_date and f.children_ids])

    print("\n" + "=" * 100)
    print("СТАТИСТИКА")
    print("=" * 100)
    print(f"Семей с датами брака и детей: {total_families_with_data}")
    print(f"Критические аномалии (ребёнок до свадьбы): {len(impossible)}")
    print(f"Явная добрачная беременность (< 100 дней): {len(very_suspicious)}")
    print(f"Подозрительные случаи (< {threshold_days} дней): {len(suspicious)}")


def main():
    parser = argparse.ArgumentParser(
        description='Проверка дат рождения первых детей относительно даты брака'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--threshold', type=int, default=260,
                        help='Порог в днях для подозрительных случаев (по умолчанию: 260)')

    args = parser.parse_args()
    analyze_first_children(args.gedcom_file, args.threshold)


if __name__ == '__main__':
    main()
