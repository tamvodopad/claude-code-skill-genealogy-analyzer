#!/usr/bin/env python3
"""
Анализ сиблингов (братьев и сестёр) в генеалогическом древе.
Интервалы между рождениями, паттерны смертности, порядок рождения.

Использование:
    python3 sibling_analysis.py tree.ged
    python3 sibling_analysis.py tree.ged --before 1920
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
class SiblingGroup:
    """Группа сиблингов (дети одной семьи)."""
    family: Family
    children: List[Person]
    birth_intervals: List[int]  # дни между рождениями
    mortality_before_5: int     # умерших до 5 лет
    sex_ratio: Tuple[int, int]  # (мальчики, девочки)


def get_birth_date_sortable(person: Person) -> Tuple[int, int, int]:
    """Получить дату рождения для сортировки."""
    if person.birth_date:
        return (person.birth_date.year, person.birth_date.month, person.birth_date.day)
    if person.birth_year:
        return (person.birth_year, 6, 15)
    return (9999, 1, 1)


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def get_death_year(person: Person) -> Optional[int]:
    """Получить год смерти."""
    if person.death_date:
        return person.death_date.year
    return person.death_year


def calculate_birth_interval_days(child1: Person, child2: Person) -> Optional[int]:
    """Вычислить интервал между рождениями в днях."""
    if child1.birth_date and child2.birth_date:
        delta = child2.birth_date - child1.birth_date
        return delta.days

    # Если только годы — примерно
    year1 = get_birth_year(child1)
    year2 = get_birth_year(child2)
    if year1 and year2:
        return (year2 - year1) * 365

    return None


def died_before_age(person: Person, age: int) -> bool:
    """Проверка, умер ли человек до определённого возраста."""
    birth_year = get_birth_year(person)
    death_year = get_death_year(person)

    if birth_year and death_year:
        return (death_year - birth_year) < age

    # Если год смерти = году рождения
    if birth_year and death_year and birth_year == death_year:
        return True

    return False


def analyze_sibling_group(family: Family, data: GedcomData) -> Optional[SiblingGroup]:
    """Анализ группы сиблингов."""
    if not family.children_ids or len(family.children_ids) < 2:
        return None

    children = []
    for child_id in family.children_ids:
        child = data.get_person(child_id)
        if child:
            children.append(child)

    if len(children) < 2:
        return None

    # Сортируем по дате рождения
    children.sort(key=get_birth_date_sortable)

    # Интервалы между рождениями
    intervals = []
    for i in range(len(children) - 1):
        interval = calculate_birth_interval_days(children[i], children[i+1])
        if interval and 100 < interval < 10000:  # Реалистичный интервал
            intervals.append(interval)

    # Смертность до 5 лет
    mortality = sum(1 for c in children if died_before_age(c, 5))

    # Соотношение полов
    males = sum(1 for c in children if c.sex == 'M')
    females = sum(1 for c in children if c.sex == 'F')

    return SiblingGroup(
        family=family,
        children=children,
        birth_intervals=intervals,
        mortality_before_5=mortality,
        sex_ratio=(males, females)
    )


def analyze_all_siblings(data: GedcomData, before_year: Optional[int] = None) -> Dict:
    """Анализ всех групп сиблингов."""
    stats = {
        'total_families': 0,
        'families_with_2plus': 0,
        'all_intervals': [],
        'intervals_by_order': defaultdict(list),  # 1st→2nd, 2nd→3rd, etc.
        'family_sizes': [],
        'mortality_rates': [],
        'sex_ratios': {'M': 0, 'F': 0},
        'sibling_groups': [],
        'large_families': [],  # 8+ детей
        'short_intervals': [],  # < 1 года
        'long_intervals': [],   # > 5 лет
    }

    for family_id, family in data.families.items():
        # Фильтр по году
        if before_year:
            # Проверяем по году брака или первого ребёнка
            check_year = family.marriage_year
            if family.marriage_date:
                check_year = family.marriage_date.year
            if not check_year and family.children_ids:
                first_child = data.get_person(family.children_ids[0])
                if first_child:
                    check_year = get_birth_year(first_child)
            if check_year and check_year > before_year:
                continue

        stats['total_families'] += 1

        group = analyze_sibling_group(family, data)
        if not group:
            continue

        stats['families_with_2plus'] += 1
        stats['sibling_groups'].append(group)
        stats['family_sizes'].append(len(group.children))

        # Интервалы
        stats['all_intervals'].extend(group.birth_intervals)

        for i, interval in enumerate(group.birth_intervals):
            order_key = f"{i+1}→{i+2}"
            stats['intervals_by_order'][order_key].append(interval)

            # Короткие интервалы (< 1 года = 365 дней)
            if interval < 365:
                stats['short_intervals'].append({
                    'family': family,
                    'interval_days': interval,
                    'children': (group.children[i], group.children[i+1])
                })

            # Длинные интервалы (> 5 лет)
            if interval > 365 * 5:
                stats['long_intervals'].append({
                    'family': family,
                    'interval_days': interval,
                    'children': (group.children[i], group.children[i+1])
                })

        # Смертность
        if len(group.children) > 0:
            mortality_rate = group.mortality_before_5 / len(group.children)
            stats['mortality_rates'].append(mortality_rate)

        # Пол
        stats['sex_ratios']['M'] += group.sex_ratio[0]
        stats['sex_ratios']['F'] += group.sex_ratio[1]

        # Большие семьи
        if len(group.children) >= 8:
            stats['large_families'].append(group)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ сиблингов в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Анализировать только семьи до указанного года')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ СИБЛИНГОВ (БРАТЬЕВ И СЕСТЁР)")
    if args.before:
        output_lines.append(f"(семьи до {args.before} года)")
    output_lines.append("=" * 100)

    stats = analyze_all_siblings(data, args.before)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего семей: {stats['total_families']}")
    output_lines.append(f"   Семей с 2+ детьми: {stats['families_with_2plus']}")

    if stats['family_sizes']:
        output_lines.append(f"\n👶 РАЗМЕР СЕМЕЙ:")
        output_lines.append(f"   Среднее число детей: {statistics.mean(stats['family_sizes']):.1f}")
        output_lines.append(f"   Медиана: {statistics.median(stats['family_sizes']):.1f}")
        output_lines.append(f"   Максимум: {max(stats['family_sizes'])}")

        # Распределение
        size_counts = defaultdict(int)
        for s in stats['family_sizes']:
            size_counts[s] += 1

        output_lines.append("\n   Распределение:")
        max_count = max(size_counts.values())
        for size in sorted(size_counts.keys()):
            count = size_counts[size]
            bar_len = int(30 * count / max_count)
            bar = "█" * bar_len
            pct = count / len(stats['family_sizes']) * 100
            output_lines.append(f"      {size:>2} детей: {bar} {count} ({pct:.1f}%)")

    # Интервалы между рождениями
    if stats['all_intervals']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("⏱️ ИНТЕРВАЛЫ МЕЖДУ РОЖДЕНИЯМИ")
        output_lines.append("=" * 100)

        intervals_months = [i / 30 for i in stats['all_intervals']]
        output_lines.append(f"\n   Всего интервалов: {len(intervals_months)}")
        output_lines.append(f"   Средний интервал: {statistics.mean(intervals_months):.1f} мес. ({statistics.mean(intervals_months)/12:.1f} лет)")
        output_lines.append(f"   Медиана: {statistics.median(intervals_months):.1f} мес.")
        output_lines.append(f"   Минимум: {min(intervals_months):.1f} мес.")
        output_lines.append(f"   Максимум: {max(intervals_months):.1f} мес.")

        # По порядку рождения
        output_lines.append("\n   По порядку рождения:")
        for order in sorted(stats['intervals_by_order'].keys())[:6]:
            intervals = stats['intervals_by_order'][order]
            if intervals:
                avg_months = statistics.mean(intervals) / 30
                output_lines.append(f"      {order} ребёнок: {avg_months:.1f} мес. (n={len(intervals)})")

        # Гистограмма интервалов
        output_lines.append("\n   Распределение интервалов:")
        buckets = defaultdict(int)
        for i in intervals_months:
            bucket = int(i // 12)  # по годам
            buckets[bucket] += 1

        max_count = max(buckets.values()) if buckets else 1
        for bucket in sorted(buckets.keys())[:8]:
            count = buckets[bucket]
            bar_len = int(30 * count / max_count)
            bar = "█" * bar_len
            pct = count / len(intervals_months) * 100
            output_lines.append(f"      {bucket}-{bucket+1} лет: {bar} {count} ({pct:.1f}%)")

    # Короткие интервалы
    if stats['short_intervals']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"⚠️ КОРОТКИЕ ИНТЕРВАЛЫ (< 1 года): {len(stats['short_intervals'])}")
        output_lines.append("=" * 100)

        sorted_short = sorted(stats['short_intervals'], key=lambda x: x['interval_days'])
        for item in sorted_short[:10]:
            c1, c2 = item['children']
            months = item['interval_days'] / 30
            husband = data.get_person(item['family'].husband_id)
            wife = data.get_person(item['family'].wife_id)
            parents = f"{husband.name if husband else '?'} + {wife.name if wife else '?'}"
            output_lines.append(f"\n   {months:.1f} мес.: {c1.name} → {c2.name}")
            output_lines.append(f"      Родители: {parents}")

        if len(stats['short_intervals']) > 10:
            output_lines.append(f"\n   ... и ещё {len(stats['short_intervals']) - 10}")

    # Длинные интервалы
    if stats['long_intervals']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"🔍 ДЛИННЫЕ ИНТЕРВАЛЫ (> 5 лет): {len(stats['long_intervals'])}")
        output_lines.append("=" * 100)
        output_lines.append("   (возможны пропущенные дети или повторный брак)")

        sorted_long = sorted(stats['long_intervals'], key=lambda x: -x['interval_days'])
        for item in sorted_long[:10]:
            c1, c2 = item['children']
            years = item['interval_days'] / 365
            output_lines.append(f"\n   {years:.1f} лет: {c1.name} ({get_birth_year(c1)}) → {c2.name} ({get_birth_year(c2)})")

    # Смертность
    if stats['mortality_rates']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("💀 ДЕТСКАЯ СМЕРТНОСТЬ В СЕМЬЯХ (до 5 лет)")
        output_lines.append("=" * 100)

        avg_mortality = statistics.mean(stats['mortality_rates']) * 100
        output_lines.append(f"\n   Средняя смертность: {avg_mortality:.1f}%")

        # Семьи с высокой смертностью
        high_mortality = [g for g in stats['sibling_groups']
                         if len(g.children) >= 4 and g.mortality_before_5 / len(g.children) > 0.5]
        if high_mortality:
            output_lines.append(f"\n   Семьи с высокой смертностью (>50%, 4+ детей): {len(high_mortality)}")
            for g in high_mortality[:5]:
                husband = data.get_person(g.family.husband_id)
                wife = data.get_person(g.family.wife_id)
                rate = g.mortality_before_5 / len(g.children) * 100
                output_lines.append(f"      {husband.name if husband else '?'} + {wife.name if wife else '?'}: "
                                   f"{g.mortality_before_5}/{len(g.children)} ({rate:.0f}%)")

    # Соотношение полов
    total_m = stats['sex_ratios']['M']
    total_f = stats['sex_ratios']['F']
    if total_m + total_f > 0:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👫 СООТНОШЕНИЕ ПОЛОВ")
        output_lines.append("=" * 100)

        ratio = total_m / total_f if total_f > 0 else 0
        output_lines.append(f"\n   Мальчиков: {total_m}")
        output_lines.append(f"   Девочек: {total_f}")
        output_lines.append(f"   Соотношение М/Ж: {ratio:.2f}")
        output_lines.append(f"   (норма ~1.05, т.е. 105 мальчиков на 100 девочек)")

    # Большие семьи
    if stats['large_families']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"🏆 БОЛЬШИЕ СЕМЬИ (8+ детей): {len(stats['large_families'])}")
        output_lines.append("=" * 100)

        sorted_large = sorted(stats['large_families'], key=lambda x: -len(x.children))
        for g in sorted_large[:10]:
            husband = data.get_person(g.family.husband_id)
            wife = data.get_person(g.family.wife_id)
            survived = len(g.children) - g.mortality_before_5
            output_lines.append(f"\n   {len(g.children)} детей ({survived} дожили до 5 лет):")
            output_lines.append(f"      {husband.name if husband else '?'} + {wife.name if wife else '?'}")
            children_names = [c.given_name or c.name for c in g.children[:8]]
            output_lines.append(f"      Дети: {', '.join(children_names)}" +
                              (f"..." if len(g.children) > 8 else ""))

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Типичные интервалы между рождениями:

   • 18-24 месяца — при грудном вскармливании (лактационная аменорея)
   • 12-15 месяцев — при раннем отлучении или смерти младенца
   • < 12 месяцев — возможно близнецы или ошибка в данных
   • > 5 лет — возможны пропущенные дети, болезнь, разлука

   Короткие интервалы (< 1 года) могут указывать на:
   • Смерть предыдущего младенца
   • Близнецов (проверить даты)
   • Ошибку в записи

   Длинные интервалы (> 5 лет) могут указывать на:
   • Пропущенных/незаписанных детей
   • Болезнь матери
   • Военную службу отца
   • Повторный брак (дети от разных матерей)
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
