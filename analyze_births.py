#!/usr/bin/env python3
"""
Аналитика по датам рождения из GEDCOM файла.
Распределение по годам, месяцам, сезонам зачатия.

Использование:
    python3 analyze_births.py tree.ged
"""

import re
import sys
import argparse
from datetime import date
from collections import defaultdict
from typing import Optional, Tuple, List, Dict


def parse_gedcom_date(date_str: str) -> Tuple[Optional[date], Optional[int], bool]:
    """
    Парсинг даты из GEDCOM формата.
    Возвращает (полная_дата, год, is_julian).
    """
    if not date_str:
        return None, None, False

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
                return date(int(year), months[month_str], int(day)), int(year), is_julian
            except ValueError:
                pass

    # Только год
    year_match = re.search(r'(\d{4})', clean_str)
    if year_match:
        return None, int(year_match.group(1)), is_julian

    return None, None, is_julian


def parse_gedcom(filepath: str) -> List[Dict]:
    """Парсинг GEDCOM файла для извлечения данных о рождениях."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    births = []
    current_id = None
    in_birt = False
    current_name = ""
    current_sex = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("0 "):
            match = re.match(r'0 (@\w+@) INDI', line)
            if match:
                current_id = match.group(1)
                current_name = ""
                current_sex = ""
            else:
                current_id = None
            in_birt = False
            continue

        if current_id:
            if line.startswith("1 NAME "):
                current_name = line[7:].replace('/', '').strip()
            elif line.startswith("1 SEX "):
                current_sex = line[6:].strip()
            elif line.startswith("1 BIRT"):
                in_birt = True
            elif line.startswith("1 ") and not line.startswith("1 BIRT"):
                in_birt = False
            elif line.startswith("2 DATE") and in_birt:
                date_str = line[7:].strip()
                full_date, year, is_julian = parse_gedcom_date(date_str)

                if full_date or year:
                    births.append({
                        'id': current_id,
                        'name': current_name,
                        'sex': current_sex,
                        'date': full_date,
                        'year': year,
                        'julian': is_julian,
                        'raw': date_str
                    })

    return births


def analyze_births(filepath: str, show_list: bool = False):
    """Основной анализ рождений."""
    print(f"Парсинг GEDCOM файла: {filepath}")
    births = parse_gedcom(filepath)
    print(f"Найдено записей о рождении: {len(births)}\n")

    # Статистика
    full_dates = [b for b in births if b['date']]
    year_only = [b for b in births if not b['date'] and b['year']]
    julian_count = sum(1 for b in full_dates if b['julian'])
    gregorian_count = len(full_dates) - julian_count

    # Распределения
    by_year = defaultdict(int)
    by_month = defaultdict(int)
    by_decade = defaultdict(int)
    by_sex = defaultdict(int)

    for b in births:
        if b['year']:
            by_year[b['year']] += 1
            by_decade[(b['year'] // 10) * 10] += 1
        if b['date']:
            by_month[b['date'].month] += 1
        if b['sex']:
            by_sex[b['sex']] += 1

    # Вывод
    print("=" * 100)
    print("АНАЛИТИКА ПО ДАТАМ РОЖДЕНИЯ")
    print("=" * 100)
    print(f"\nВсего записей о рождении: {len(births)}")
    print(f"  ├─ С полной датой: {len(full_dates)}")
    print(f"  │    ├─ Юлианский календарь: {julian_count}")
    print(f"  │    └─ Григорианский/без метки: {gregorian_count}")
    print(f"  └─ Только год: {len(year_only)}")

    print(f"\nПо полу:")
    print(f"  ├─ Мужчины: {by_sex.get('M', 0)}")
    print(f"  └─ Женщины: {by_sex.get('F', 0)}")

    # Распределение по десятилетиям
    print("\n" + "=" * 100)
    print("РАСПРЕДЕЛЕНИЕ ПО ДЕСЯТИЛЕТИЯМ")
    print("=" * 100)
    max_count = max(by_decade.values()) if by_decade else 1
    for decade in sorted(by_decade.keys()):
        count = by_decade[decade]
        bar_len = int(50 * count / max_count)
        bar = "█" * bar_len
        print(f"{decade}s: {bar} {count}")

    # Распределение по месяцам
    if full_dates:
        print("\n" + "=" * 100)
        print("РАСПРЕДЕЛЕНИЕ ПО МЕСЯЦАМ (только полные даты)")
        print("=" * 100)
        month_names = {
            1: "Январь  ", 2: "Февраль ", 3: "Март    ", 4: "Апрель  ",
            5: "Май     ", 6: "Июнь    ", 7: "Июль    ", 8: "Август  ",
            9: "Сентябрь", 10: "Октябрь ", 11: "Ноябрь  ", 12: "Декабрь "
        }
        max_month = max(by_month.values()) if by_month else 1
        for month in range(1, 13):
            count = by_month[month]
            bar_len = int(40 * count / max_month)
            bar = "█" * bar_len
            pct = 100 * count / len(full_dates)
            print(f"{month_names[month]}: {bar} {count} ({pct:.1f}%)")

        # Сезоны зачатия
        print("\n" + "=" * 100)
        print("РАСПРЕДЕЛЕНИЕ ПО СЕЗОНАМ ЗАЧАТИЯ")
        print("(рождение минус ~9 месяцев)")
        print("=" * 100)
        conception_seasons = {
            "Весна (март-май)": 0,
            "Лето (июнь-авг)": 0,
            "Осень (сен-ноя)": 0,
            "Зима (дек-фев)": 0
        }
        for b in full_dates:
            birth_month = b['date'].month
            conception_month = (birth_month - 9) % 12
            if conception_month == 0:
                conception_month = 12

            if conception_month in [3, 4, 5]:
                conception_seasons["Весна (март-май)"] += 1
            elif conception_month in [6, 7, 8]:
                conception_seasons["Лето (июнь-авг)"] += 1
            elif conception_month in [9, 10, 11]:
                conception_seasons["Осень (сен-ноя)"] += 1
            else:
                conception_seasons["Зима (дек-фев)"] += 1

        for season, count in conception_seasons.items():
            pct = 100 * count / len(full_dates)
            bar_len = int(40 * count / len(full_dates) * 4)
            bar = "█" * bar_len
            print(f"{season}: {bar} {count} ({pct:.1f}%)")

    # Самые ранние и поздние
    if full_dates:
        print("\n" + "=" * 100)
        print("САМЫЕ РАННИЕ И ПОЗДНИЕ РОЖДЕНИЯ")
        print("=" * 100)
        sorted_births = sorted(full_dates, key=lambda x: x['date'])

        print("\n📅 Самые ранние:")
        for b in sorted_births[:5]:
            julian_mark = " (ст.ст.)" if b['julian'] else ""
            print(f"   {b['date'].strftime('%d.%m.%Y')}{julian_mark} — {b['name']}")

        print("\n📅 Самые поздние:")
        for b in sorted_births[-5:]:
            julian_mark = " (ст.ст.)" if b['julian'] else ""
            print(f"   {b['date'].strftime('%d.%m.%Y')}{julian_mark} — {b['name']}")

    # Статистика по годам (пиковые)
    if by_year:
        print("\n" + "=" * 100)
        print("ПИКОВЫЕ ГОДЫ РОЖДЕНИЙ (топ-10)")
        print("=" * 100)
        top_years = sorted(by_year.items(), key=lambda x: -x[1])[:10]
        for year, count in top_years:
            print(f"   {year}: {count} рождений")

    # Список всех (опционально)
    if show_list and full_dates:
        print("\n" + "=" * 100)
        print("ПОЛНЫЙ СПИСОК РОЖДЕНИЙ С ДАТАМИ")
        print("=" * 100)
        sorted_births = sorted(full_dates, key=lambda x: x['date'])
        for b in sorted_births:
            julian_mark = " (ст.ст.)" if b['julian'] else ""
            sex_mark = "♂" if b['sex'] == 'M' else "♀" if b['sex'] == 'F' else "?"
            print(f"{b['date'].strftime('%d.%m.%Y')}{julian_mark} {sex_mark} {b['name']}")


def main():
    parser = argparse.ArgumentParser(
        description='Аналитика по датам рождения из GEDCOM файла'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--list', action='store_true',
                        help='Показать полный список рождений')

    args = parser.parse_args()
    analyze_births(args.gedcom_file, args.list)


if __name__ == '__main__':
    main()
