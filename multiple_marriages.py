#!/usr/bin/env python3
"""
Анализ повторных браков в генеалогическом древе.
Вдовство, количество браков, дети от разных браков.

Использование:
    python3 multiple_marriages.py tree.ged
    python3 multiple_marriages.py tree.ged --before 1920
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class PersonMarriages:
    """Данные о браках персоны."""
    person: Person
    marriages: List[Family]
    spouses: List[Person]
    marriage_years: List[Optional[int]]
    spouse_death_years: List[Optional[int]]
    children_per_marriage: List[int]
    widowed_before_remarriage: List[bool]


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


def get_marriage_year(family: Family) -> Optional[int]:
    """Получить год брака."""
    if family.marriage_date:
        return family.marriage_date.year
    return family.marriage_year


def analyze_person_marriages(person: Person, data: GedcomData) -> Optional[PersonMarriages]:
    """Анализ браков одной персоны."""
    if not person.spouse_family_ids or len(person.spouse_family_ids) < 2:
        return None

    marriages = []
    spouses = []
    marriage_years = []
    spouse_death_years = []
    children_counts = []
    widowed = []

    for fam_id in person.spouse_family_ids:
        family = data.families.get(fam_id)
        if not family:
            continue

        marriages.append(family)

        # Определяем супруга
        if person.sex == 'M':
            spouse_id = family.wife_id
        else:
            spouse_id = family.husband_id

        spouse = data.get_person(spouse_id) if spouse_id else None
        spouses.append(spouse)

        # Год брака
        m_year = get_marriage_year(family)
        marriage_years.append(m_year)

        # Год смерти супруга
        s_death = get_death_year(spouse) if spouse else None
        spouse_death_years.append(s_death)

        # Количество детей
        children_counts.append(len(family.children_ids))

    if len(marriages) < 2:
        return None

    # Сортируем по году брака
    combined = list(zip(marriages, spouses, marriage_years, spouse_death_years, children_counts))
    combined.sort(key=lambda x: x[2] if x[2] else 9999)

    marriages, spouses, marriage_years, spouse_death_years, children_counts = zip(*combined)
    marriages = list(marriages)
    spouses = list(spouses)
    marriage_years = list(marriage_years)
    spouse_death_years = list(spouse_death_years)
    children_counts = list(children_counts)

    # Определяем, было ли вдовство перед следующим браком
    widowed = []
    for i in range(len(marriages)):
        if i == 0:
            widowed.append(False)
        else:
            prev_spouse_death = spouse_death_years[i-1]
            curr_marriage = marriage_years[i]
            if prev_spouse_death and curr_marriage and prev_spouse_death < curr_marriage:
                widowed.append(True)
            else:
                widowed.append(False)

    return PersonMarriages(
        person=person,
        marriages=marriages,
        spouses=spouses,
        marriage_years=marriage_years,
        spouse_death_years=spouse_death_years,
        children_per_marriage=children_counts,
        widowed_before_remarriage=widowed
    )


def analyze_all_multiple_marriages(data: GedcomData, before_year: Optional[int] = None) -> Dict:
    """Анализ всех повторных браков."""
    stats = {
        'total_persons': 0,
        'persons_with_multiple': 0,
        'men_multiple': 0,
        'women_multiple': 0,
        'max_marriages': 0,
        'by_count': defaultdict(int),  # количество браков -> количество людей
        'cases': [],
        'widowed_remarriages': 0,
        'interval_between_marriages': [],
        'children_distribution': [],  # (браков, всего детей)
    }

    processed = set()

    for person_id, person in data.persons.items():
        if person_id in processed:
            continue
        processed.add(person_id)

        stats['total_persons'] += 1

        pm = analyze_person_marriages(person, data)
        if not pm:
            continue

        # Фильтр по году (проверяем первый брак)
        if before_year and pm.marriage_years[0] and pm.marriage_years[0] > before_year:
            continue

        stats['persons_with_multiple'] += 1

        if person.sex == 'M':
            stats['men_multiple'] += 1
        else:
            stats['women_multiple'] += 1

        num_marriages = len(pm.marriages)
        stats['by_count'][num_marriages] += 1

        if num_marriages > stats['max_marriages']:
            stats['max_marriages'] = num_marriages

        stats['cases'].append(pm)

        # Вдовство
        if any(pm.widowed_before_remarriage):
            stats['widowed_remarriages'] += 1

        # Интервалы между браками
        for i in range(1, len(pm.marriage_years)):
            if pm.marriage_years[i] and pm.marriage_years[i-1]:
                interval = pm.marriage_years[i] - pm.marriage_years[i-1]
                if 0 < interval < 50:
                    stats['interval_between_marriages'].append(interval)

        # Распределение детей
        total_children = sum(pm.children_per_marriage)
        stats['children_distribution'].append((num_marriages, total_children))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ повторных браков в генеалогическом древе'
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
    output_lines.append("АНАЛИЗ ПОВТОРНЫХ БРАКОВ")
    if args.before:
        output_lines.append(f"(браки до {args.before} года)")
    output_lines.append("=" * 100)

    stats = analyze_all_multiple_marriages(data, args.before)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего персон: {stats['total_persons']}")
    output_lines.append(f"   С несколькими браками: {stats['persons_with_multiple']}")

    if stats['total_persons'] > 0:
        pct = stats['persons_with_multiple'] / stats['total_persons'] * 100
        output_lines.append(f"   Процент: {pct:.1f}%")

    output_lines.append(f"\n   Мужчин с несколькими браками: {stats['men_multiple']}")
    output_lines.append(f"   Женщин с несколькими браками: {stats['women_multiple']}")
    output_lines.append(f"   Максимум браков у одного человека: {stats['max_marriages']}")

    # Распределение по количеству браков
    if stats['by_count']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("💍 РАСПРЕДЕЛЕНИЕ ПО КОЛИЧЕСТВУ БРАКОВ")
        output_lines.append("=" * 100)

        for count in sorted(stats['by_count'].keys()):
            num = stats['by_count'][count]
            output_lines.append(f"   {count} брака/браков: {num} человек")

    # Интервалы между браками
    if stats['interval_between_marriages']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("⏱️ ИНТЕРВАЛ МЕЖДУ БРАКАМИ")
        output_lines.append("=" * 100)

        intervals = stats['interval_between_marriages']
        import statistics
        output_lines.append(f"\n   Средний интервал: {statistics.mean(intervals):.1f} лет")
        output_lines.append(f"   Медиана: {statistics.median(intervals):.1f} лет")
        output_lines.append(f"   Минимум: {min(intervals)} лет")
        output_lines.append(f"   Максимум: {max(intervals)} лет")

        # Быстрые повторные браки (< 2 лет)
        quick = [i for i in intervals if i < 2]
        if quick:
            output_lines.append(f"\n   Быстрые повторные браки (<2 лет): {len(quick)}")

    # Вдовство
    output_lines.append("\n" + "=" * 100)
    output_lines.append("⚰️ ВДОВСТВО И ПОВТОРНЫЙ БРАК")
    output_lines.append("=" * 100)

    output_lines.append(f"\n   Повторные браки после смерти супруга: {stats['widowed_remarriages']}")
    if stats['persons_with_multiple'] > 0:
        pct = stats['widowed_remarriages'] / stats['persons_with_multiple'] * 100
        output_lines.append(f"   Процент от повторных браков: {pct:.1f}%")

    # Детальные случаи
    if stats['cases']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📋 СЛУЧАИ ПОВТОРНЫХ БРАКОВ")
        output_lines.append("=" * 100)

        # Сортируем по количеству браков
        sorted_cases = sorted(stats['cases'], key=lambda x: -len(x.marriages))

        for pm in sorted_cases[:20]:
            output_lines.append(f"\n   👤 {pm.person.name} ({len(pm.marriages)} брака/браков):")

            for i, (spouse, m_year, s_death, children) in enumerate(
                    zip(pm.spouses, pm.marriage_years, pm.spouse_death_years, pm.children_per_marriage), 1):

                spouse_name = spouse.name if spouse else "?"
                year_str = str(m_year) if m_year else "?"
                death_str = f", ум. {s_death}" if s_death else ""
                widowed_str = " [вдовство]" if i > 1 and pm.widowed_before_remarriage[i-1] else ""

                output_lines.append(f"      {i}. {spouse_name} ({year_str}{death_str}), детей: {children}{widowed_str}")

        if len(stats['cases']) > 20:
            output_lines.append(f"\n   ... и ещё {len(stats['cases']) - 20} случаев")

    # Анализ по полу
    output_lines.append("\n" + "=" * 100)
    output_lines.append("👫 АНАЛИЗ ПО ПОЛУ")
    output_lines.append("=" * 100)

    men_cases = [pm for pm in stats['cases'] if pm.person.sex == 'M']
    women_cases = [pm for pm in stats['cases'] if pm.person.sex == 'F']

    if men_cases:
        avg_marriages_men = sum(len(pm.marriages) for pm in men_cases) / len(men_cases)
        output_lines.append(f"\n   Мужчины:")
        output_lines.append(f"      Среднее число браков: {avg_marriages_men:.1f}")
        output_lines.append(f"      Максимум: {max(len(pm.marriages) for pm in men_cases)}")

    if women_cases:
        avg_marriages_women = sum(len(pm.marriages) for pm in women_cases) / len(women_cases)
        output_lines.append(f"\n   Женщины:")
        output_lines.append(f"      Среднее число браков: {avg_marriages_women:.1f}")
        output_lines.append(f"      Максимум: {max(len(pm.marriages) for pm in women_cases)}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Причины повторных браков в России (до 1917):

   • Смерть супруга (высокая смертность, особенно при родах)
   • Необходимость вести хозяйство
   • Потребность в детях (наследниках)

   Особенности:
   • Мужчины чаще вступали в повторный брак
   • Вдовцы с детьми женились быстрее (нужна хозяйка)
   • Вдовы реже выходили заму|<ужи, особенно с детьми
   • Повторный брак часто с вдовой/вдовцом

   Интервалы:
   • < 1 года — очень быстро, хозяйственная необходимость
   • 1-2 года — типично для вдовцов
   • > 5 лет — нетипично, требует объяснения

   ⚠️ Если смерть супруга не записана, но есть повторный брак —
   возможно, данные о смерти утеряны.
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
