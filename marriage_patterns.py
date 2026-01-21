#!/usr/bin/env python3
"""
Анализ паттернов браков в генеалогическом древе.
Возраст вступления в брак, эндогамия/экзогамия, разница в возрасте.

Использование:
    python3 marriage_patterns.py tree.ged
    python3 marriage_patterns.py tree.ged --before 1920
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
import statistics

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class MarriageData:
    """Данные о браке."""
    family: Family
    husband: Person
    wife: Person
    marriage_year: Optional[int]
    husband_age: Optional[int]
    wife_age: Optional[int]
    age_difference: Optional[int]  # муж - жена
    same_place: bool  # из одного места
    husband_place: Optional[str]
    wife_place: Optional[str]


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def get_marriage_year(family: Family) -> Optional[int]:
    """Получить год брака."""
    if family.marriage_date:
        return family.marriage_date.year
    return family.marriage_year


def extract_main_place(place: str) -> str:
    """Извлечь основное место (первая часть до запятой)."""
    if not place:
        return ""
    return place.split(',')[0].strip().lower()


def normalize_place(place: str) -> str:
    """Нормализовать место для сравнения."""
    if not place:
        return ""
    p = place.lower().strip()
    # Убираем типичные префиксы
    for prefix in ['д.', 'д ', 'с.', 'с ', 'село ', 'деревня ', 'г.', 'г ', 'город ']:
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p.strip()


def analyze_marriage(family: Family, data: GedcomData) -> Optional[MarriageData]:
    """Анализ одного брака."""
    husband = data.get_person(family.husband_id) if family.husband_id else None
    wife = data.get_person(family.wife_id) if family.wife_id else None

    if not husband or not wife:
        return None

    marriage_year = get_marriage_year(family)
    husband_birth = get_birth_year(husband)
    wife_birth = get_birth_year(wife)

    husband_age = None
    wife_age = None
    age_diff = None

    if marriage_year:
        if husband_birth:
            husband_age = marriage_year - husband_birth
            if not (15 <= husband_age <= 70):
                husband_age = None
        if wife_birth:
            wife_age = marriage_year - wife_birth
            if not (12 <= wife_age <= 60):
                wife_age = None

    if husband_birth and wife_birth:
        age_diff = husband_birth - wife_birth  # отрицательное = муж старше
        age_diff = -age_diff  # теперь положительное = муж старше

    # Места рождения
    husband_place = normalize_place(husband.birth_place) if husband.birth_place else None
    wife_place = normalize_place(wife.birth_place) if wife.birth_place else None

    same_place = False
    if husband_place and wife_place:
        same_place = husband_place == wife_place

    return MarriageData(
        family=family,
        husband=husband,
        wife=wife,
        marriage_year=marriage_year,
        husband_age=husband_age,
        wife_age=wife_age,
        age_difference=age_diff,
        same_place=same_place,
        husband_place=husband_place,
        wife_place=wife_place
    )


def analyze_all_marriages(data: GedcomData, before_year: Optional[int] = None) -> Dict:
    """Анализ всех браков."""
    stats = {
        'total': 0,
        'with_ages': 0,
        'marriages': [],
        'husband_ages': [],
        'wife_ages': [],
        'age_differences': [],
        'same_place_count': 0,
        'different_place_count': 0,
        'place_pairs': defaultdict(int),
        'by_decade': defaultdict(lambda: {'count': 0, 'husband_ages': [], 'wife_ages': []}),
        'unusual_ages': [],
        'large_age_diff': [],
        'wife_older': [],
    }

    for family_id, family in data.families.items():
        marriage_data = analyze_marriage(family, data)
        if not marriage_data:
            continue

        # Фильтр по году
        if before_year and marriage_data.marriage_year and marriage_data.marriage_year > before_year:
            continue

        stats['total'] += 1
        stats['marriages'].append(marriage_data)

        # Возраст
        if marriage_data.husband_age:
            stats['husband_ages'].append(marriage_data.husband_age)
        if marriage_data.wife_age:
            stats['wife_ages'].append(marriage_data.wife_age)

        if marriage_data.husband_age and marriage_data.wife_age:
            stats['with_ages'] += 1

        # Разница в возрасте
        if marriage_data.age_difference is not None:
            stats['age_differences'].append(marriage_data.age_difference)

            # Большая разница (> 15 лет)
            if abs(marriage_data.age_difference) > 15:
                stats['large_age_diff'].append(marriage_data)

            # Жена старше мужа
            if marriage_data.age_difference < -3:
                stats['wife_older'].append(marriage_data)

        # Эндогамия/экзогамия
        if marriage_data.husband_place and marriage_data.wife_place:
            if marriage_data.same_place:
                stats['same_place_count'] += 1
            else:
                stats['different_place_count'] += 1
                # Записываем пару мест
                pair = tuple(sorted([marriage_data.husband_place, marriage_data.wife_place]))
                stats['place_pairs'][pair] += 1

        # По десятилетиям
        if marriage_data.marriage_year:
            decade = (marriage_data.marriage_year // 10) * 10
            stats['by_decade'][decade]['count'] += 1
            if marriage_data.husband_age:
                stats['by_decade'][decade]['husband_ages'].append(marriage_data.husband_age)
            if marriage_data.wife_age:
                stats['by_decade'][decade]['wife_ages'].append(marriage_data.wife_age)

        # Необычный возраст
        if marriage_data.husband_age and marriage_data.husband_age > 40:
            stats['unusual_ages'].append(('husband_old', marriage_data))
        if marriage_data.wife_age and marriage_data.wife_age > 35:
            stats['unusual_ages'].append(('wife_old', marriage_data))
        if marriage_data.husband_age and marriage_data.husband_age < 18:
            stats['unusual_ages'].append(('husband_young', marriage_data))
        if marriage_data.wife_age and marriage_data.wife_age < 16:
            stats['unusual_ages'].append(('wife_young', marriage_data))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ паттернов браков в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Анализировать только браки до указанного года')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ПАТТЕРНОВ БРАКОВ")
    if args.before:
        output_lines.append(f"(браки до {args.before} года)")
    output_lines.append("=" * 100)

    stats = analyze_all_marriages(data, args.before)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего браков: {stats['total']}")
    output_lines.append(f"   С известным возрастом обоих: {stats['with_ages']}")

    # Возраст вступления в брак
    if stats['husband_ages'] or stats['wife_ages']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("💍 ВОЗРАСТ ВСТУПЛЕНИЯ В БРАК")
        output_lines.append("=" * 100)

        if stats['husband_ages']:
            output_lines.append(f"\n   Мужчины:")
            output_lines.append(f"      Средний возраст: {statistics.mean(stats['husband_ages']):.1f} лет")
            output_lines.append(f"      Медиана: {statistics.median(stats['husband_ages']):.1f} лет")
            output_lines.append(f"      Диапазон: {min(stats['husband_ages'])}-{max(stats['husband_ages'])} лет")

        if stats['wife_ages']:
            output_lines.append(f"\n   Женщины:")
            output_lines.append(f"      Средний возраст: {statistics.mean(stats['wife_ages']):.1f} лет")
            output_lines.append(f"      Медиана: {statistics.median(stats['wife_ages']):.1f} лет")
            output_lines.append(f"      Диапазон: {min(stats['wife_ages'])}-{max(stats['wife_ages'])} лет")

        # Гистограмма возраста женщин
        if stats['wife_ages']:
            output_lines.append("\n   Распределение возраста невест:")
            buckets = defaultdict(int)
            for age in stats['wife_ages']:
                bucket = (age // 5) * 5
                buckets[bucket] += 1

            max_count = max(buckets.values()) if buckets else 1
            for bucket in sorted(buckets.keys()):
                if bucket < 50:
                    count = buckets[bucket]
                    bar_len = int(30 * count / max_count)
                    bar = "█" * bar_len
                    pct = count / len(stats['wife_ages']) * 100
                    output_lines.append(f"      {bucket:>2}-{bucket+4:<2}: {bar} {count} ({pct:.1f}%)")

    # Разница в возрасте
    if stats['age_differences']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📏 РАЗНИЦА В ВОЗРАСТЕ СУПРУГОВ")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   Средняя разница: {statistics.mean(stats['age_differences']):.1f} лет (муж старше)")
        output_lines.append(f"   Медиана: {statistics.median(stats['age_differences']):.1f} лет")

        # Распределение
        output_lines.append("\n   Распределение:")
        buckets = defaultdict(int)
        for diff in stats['age_differences']:
            if diff < -5:
                bucket = "жена старше на 5+"
            elif diff < 0:
                bucket = "жена старше на 1-5"
            elif diff == 0:
                bucket = "ровесники"
            elif diff <= 5:
                bucket = "муж старше на 1-5"
            elif diff <= 10:
                bucket = "муж старше на 6-10"
            else:
                bucket = "муж старше на 10+"
            buckets[bucket] += 1

        order = ["жена старше на 5+", "жена старше на 1-5", "ровесники",
                 "муж старше на 1-5", "муж старше на 6-10", "муж старше на 10+"]
        for bucket in order:
            if bucket in buckets:
                count = buckets[bucket]
                pct = count / len(stats['age_differences']) * 100
                output_lines.append(f"      {bucket}: {count} ({pct:.1f}%)")

    # Большая разница в возрасте
    if stats['large_age_diff']:
        output_lines.append(f"\n   ⚠️ Большая разница (>15 лет): {len(stats['large_age_diff'])}")
        for md in sorted(stats['large_age_diff'], key=lambda x: -abs(x.age_difference))[:5]:
            output_lines.append(f"      {md.husband.name} ({md.husband_age}) + {md.wife.name} ({md.wife_age}): "
                               f"{abs(md.age_difference)} лет")

    # Жена старше
    if stats['wife_older']:
        output_lines.append(f"\n   👩 Жена старше мужа (>3 лет): {len(stats['wife_older'])}")
        for md in stats['wife_older'][:5]:
            diff = -md.age_difference
            output_lines.append(f"      {md.wife.name} ({md.wife_age}) + {md.husband.name} ({md.husband_age}): "
                               f"жена старше на {diff} лет")

    # Эндогамия/экзогамия
    total_with_places = stats['same_place_count'] + stats['different_place_count']
    if total_with_places > 0:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🏘️ ЭНДОГАМИЯ / ЭКЗОГАМИЯ")
        output_lines.append("=" * 100)

        endo_pct = stats['same_place_count'] / total_with_places * 100
        exo_pct = stats['different_place_count'] / total_with_places * 100

        output_lines.append(f"\n   Браков с известными местами: {total_with_places}")
        output_lines.append(f"   Эндогамия (из одного места): {stats['same_place_count']} ({endo_pct:.1f}%)")
        output_lines.append(f"   Экзогамия (из разных мест): {stats['different_place_count']} ({exo_pct:.1f}%)")

        # Популярные межместные браки
        if stats['place_pairs']:
            output_lines.append("\n   Популярные межместные пары:")
            sorted_pairs = sorted(stats['place_pairs'].items(), key=lambda x: -x[1])
            for (p1, p2), count in sorted_pairs[:10]:
                if count > 1:
                    output_lines.append(f"      {p1} ↔ {p2}: {count}")

    # По десятилетиям
    if stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 ВОЗРАСТ БРАКА ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   {'Период':<12} {'Браков':<8} {'Муж (ср.)':<12} {'Жена (ср.)':<12}")
        output_lines.append("   " + "-" * 50)

        for decade in sorted(stats['by_decade'].keys()):
            d = stats['by_decade'][decade]
            h_avg = f"{statistics.mean(d['husband_ages']):.1f}" if d['husband_ages'] else "?"
            w_avg = f"{statistics.mean(d['wife_ages']):.1f}" if d['wife_ages'] else "?"
            output_lines.append(f"   {decade}s       {d['count']:<8} {h_avg:<12} {w_avg:<12}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Типичный возраст брака в России (крестьяне, XIX век):

   • Мужчины: 18-25 лет (пик ~21-22)
   • Женщины: 16-22 года (пик ~18-19)
   • Разница: муж старше на 2-5 лет

   Эндогамия (браки внутри общины):
   • Высокая (>70%) — закрытое сообщество, изолированная деревня
   • Средняя (40-70%) — типично для сельской местности
   • Низкая (<40%) — городская среда, хорошие коммуникации

   Необычные случаи:
   • Жених >35 — возможно повторный брак (вдовец)
   • Невеста >30 — редкость, возможно вдова
   • Большая разница в возрасте — часто повторный брак
   • Жена старше — нетипично, требует объяснения
""")

    # Вывод
    report = "\n".join(output_lines)
    print(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n💾 Отчёт сохранён в: {args.output}")


if __name__ == '__main__':
    main()
