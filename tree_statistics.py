#!/usr/bin/env python3
"""
Общая статистика генеалогического древа.
Полный обзор данных, метрики, распределения.

Использование:
    python3 tree_statistics.py tree.ged
    python3 tree_statistics.py tree.ged --detailed
"""

import sys
import argparse
from typing import Optional, Dict, List
from collections import defaultdict
import statistics

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


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


def calculate_statistics(data: GedcomData) -> Dict:
    """Рассчитать общую статистику."""
    stats = {
        # Основные подсчёты
        'total_persons': len(data.persons),
        'total_families': len(data.families),

        # По полу
        'males': 0,
        'females': 0,
        'unknown_sex': 0,

        # Даты рождения
        'with_birth_date': 0,
        'with_birth_year_only': 0,
        'without_birth': 0,
        'birth_years': [],

        # Даты смерти
        'with_death_date': 0,
        'with_death_year_only': 0,
        'without_death': 0,
        'death_years': [],

        # Места
        'with_birth_place': 0,
        'with_death_place': 0,
        'unique_places': set(),

        # Связи
        'with_parents': 0,
        'without_parents': 0,
        'with_spouse': 0,
        'without_spouse': 0,
        'with_children': 0,

        # Семьи
        'families_with_children': 0,
        'children_per_family': [],
        'families_with_marriage_date': 0,

        # Продолжительность жизни
        'lifespans': [],
        'lifespans_male': [],
        'lifespans_female': [],

        # По десятилетиям
        'births_by_decade': defaultdict(int),
        'deaths_by_decade': defaultdict(int),

        # Поколения (приблизительно)
        'generation_depths': [],

        # Качество данных
        'completeness_scores': [],
    }

    # Анализ персон
    for person_id, person in data.persons.items():
        # Пол
        if person.sex == 'M':
            stats['males'] += 1
        elif person.sex == 'F':
            stats['females'] += 1
        else:
            stats['unknown_sex'] += 1

        # Даты рождения
        birth_year = get_birth_year(person)
        if person.birth_date and person.birth_date.month:
            stats['with_birth_date'] += 1
        elif birth_year:
            stats['with_birth_year_only'] += 1
        else:
            stats['without_birth'] += 1

        if birth_year:
            stats['birth_years'].append(birth_year)
            decade = (birth_year // 10) * 10
            stats['births_by_decade'][decade] += 1

        # Даты смерти
        death_year = get_death_year(person)
        if person.death_date and person.death_date.month:
            stats['with_death_date'] += 1
        elif death_year:
            stats['with_death_year_only'] += 1
        else:
            stats['without_death'] += 1

        if death_year:
            stats['death_years'].append(death_year)
            decade = (death_year // 10) * 10
            stats['deaths_by_decade'][decade] += 1

        # Продолжительность жизни
        if birth_year and death_year and death_year >= birth_year:
            lifespan = death_year - birth_year
            if 0 <= lifespan <= 120:
                stats['lifespans'].append(lifespan)
                if person.sex == 'M':
                    stats['lifespans_male'].append(lifespan)
                elif person.sex == 'F':
                    stats['lifespans_female'].append(lifespan)

        # Места
        if person.birth_place:
            stats['with_birth_place'] += 1
            stats['unique_places'].add(person.birth_place.split(',')[0].strip())

        if hasattr(person, 'death_place') and person.death_place:
            stats['with_death_place'] += 1
            stats['unique_places'].add(person.death_place.split(',')[0].strip())

        # Связи
        if person.famc:
            stats['with_parents'] += 1
        else:
            stats['without_parents'] += 1

        if person.fams:
            stats['with_spouse'] += 1
        else:
            stats['without_spouse'] += 1

        # Оценка полноты данных персоны
        completeness = 0
        if birth_year:
            completeness += 20
        if person.birth_date and person.birth_date.month and person.birth_date.day:
            completeness += 10
        if person.birth_place:
            completeness += 15
        if death_year or (hasattr(person, 'living') and person.living):
            completeness += 20
        if person.death_date and person.death_date.month:
            completeness += 10
        if person.famc:
            completeness += 15
        if person.sex:
            completeness += 10

        stats['completeness_scores'].append(completeness)

    # Анализ семей
    for family_id, family in data.families.items():
        if family.children_ids:
            stats['families_with_children'] += 1
            stats['children_per_family'].append(len(family.children_ids))

            for child_id in family.children_ids:
                child = data.get_person(child_id)
                if child and (family.husband_id or family.wife_id):
                    stats['with_children'] += 1

        if family.marriage_date or family.marriage_year:
            stats['families_with_marriage_date'] += 1

    stats['unique_places'] = list(stats['unique_places'])

    return stats


def calculate_depth(person: Person, data: GedcomData, cache: Dict, direction: str = 'ancestors') -> int:
    """Рекурсивно вычислить глубину предков или потомков."""
    if person.id in cache:
        return cache[person.id]

    if direction == 'ancestors':
        if not person.famc:
            cache[person.id] = 0
            return 0

        family = data.families.get(person.famc)
        if not family:
            cache[person.id] = 0
            return 0

        max_depth = 0
        for parent_id in [family.husband_id, family.wife_id]:
            if parent_id:
                parent = data.get_person(parent_id)
                if parent:
                    depth = calculate_depth(parent, data, cache, direction)
                    max_depth = max(max_depth, depth)

        result = max_depth + 1
        cache[person.id] = result
        return result

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Общая статистика генеалогического древа'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--detailed', action='store_true',
                        help='Показать детальную статистику')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("ОБЩАЯ СТАТИСТИКА ГЕНЕАЛОГИЧЕСКОГО ДРЕВА")
    output_lines.append("=" * 100)

    stats = calculate_statistics(data)

    # Основная статистика
    output_lines.append(f"\n📊 ОСНОВНЫЕ ПОКАЗАТЕЛИ:")
    output_lines.append(f"   Всего персон: {stats['total_persons']}")
    output_lines.append(f"   Всего семей: {stats['total_families']}")

    # По полу
    output_lines.append(f"\n👥 РАСПРЕДЕЛЕНИЕ ПО ПОЛУ:")
    output_lines.append(f"   Мужчин: {stats['males']} ({stats['males']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"   Женщин: {stats['females']} ({stats['females']/stats['total_persons']*100:.1f}%)")
    if stats['unknown_sex'] > 0:
        output_lines.append(f"   Пол не указан: {stats['unknown_sex']}")

    # Временной охват
    if stats['birth_years']:
        output_lines.append(f"\n📅 ВРЕМЕННОЙ ОХВАТ:")
        output_lines.append(f"   Самое раннее рождение: {min(stats['birth_years'])}")
        output_lines.append(f"   Самое позднее рождение: {max(stats['birth_years'])}")
        output_lines.append(f"   Охват: {max(stats['birth_years']) - min(stats['birth_years'])} лет")

    # Качество данных
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📋 КАЧЕСТВО ДАННЫХ")
    output_lines.append("=" * 100)

    output_lines.append(f"\n   Даты рождения:")
    output_lines.append(f"      Полная дата: {stats['with_birth_date']} ({stats['with_birth_date']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      Только год: {stats['with_birth_year_only']} ({stats['with_birth_year_only']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      Нет данных: {stats['without_birth']} ({stats['without_birth']/stats['total_persons']*100:.1f}%)")

    output_lines.append(f"\n   Даты смерти:")
    output_lines.append(f"      Полная дата: {stats['with_death_date']} ({stats['with_death_date']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      Только год: {stats['with_death_year_only']} ({stats['with_death_year_only']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      Нет данных: {stats['without_death']} ({stats['without_death']/stats['total_persons']*100:.1f}%)")

    output_lines.append(f"\n   Места:")
    output_lines.append(f"      С местом рождения: {stats['with_birth_place']} ({stats['with_birth_place']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      С местом смерти: {stats['with_death_place']} ({stats['with_death_place']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      Уникальных мест: {len(stats['unique_places'])}")

    # Связи
    output_lines.append(f"\n   Связи:")
    output_lines.append(f"      С известными родителями: {stats['with_parents']} ({stats['with_parents']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      Конечные предки: {stats['without_parents']} ({stats['without_parents']/stats['total_persons']*100:.1f}%)")
    output_lines.append(f"      В браке: {stats['with_spouse']} ({stats['with_spouse']/stats['total_persons']*100:.1f}%)")

    # Общая оценка качества
    if stats['completeness_scores']:
        avg_completeness = statistics.mean(stats['completeness_scores'])
        output_lines.append(f"\n   📊 Средняя полнота данных: {avg_completeness:.1f}%")

        excellent = sum(1 for s in stats['completeness_scores'] if s >= 80)
        good = sum(1 for s in stats['completeness_scores'] if 50 <= s < 80)
        fair = sum(1 for s in stats['completeness_scores'] if 30 <= s < 50)
        poor = sum(1 for s in stats['completeness_scores'] if s < 30)

        output_lines.append(f"      Отлично (80%+): {excellent}")
        output_lines.append(f"      Хорошо (50-79%): {good}")
        output_lines.append(f"      Удовлетворительно (30-49%): {fair}")
        output_lines.append(f"      Плохо (<30%): {poor}")

    # Продолжительность жизни
    if stats['lifespans']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("⏳ ПРОДОЛЖИТЕЛЬНОСТЬ ЖИЗНИ")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   Всего с известной продолжительностью: {len(stats['lifespans'])}")
        output_lines.append(f"   Средняя: {statistics.mean(stats['lifespans']):.1f} лет")
        output_lines.append(f"   Медиана: {statistics.median(stats['lifespans']):.1f} лет")
        output_lines.append(f"   Минимум: {min(stats['lifespans'])} лет")
        output_lines.append(f"   Максимум: {max(stats['lifespans'])} лет")

        if stats['lifespans_male']:
            output_lines.append(f"\n   Мужчины:")
            output_lines.append(f"      Средняя: {statistics.mean(stats['lifespans_male']):.1f} лет")
            output_lines.append(f"      Медиана: {statistics.median(stats['lifespans_male']):.1f} лет")

        if stats['lifespans_female']:
            output_lines.append(f"\n   Женщины:")
            output_lines.append(f"      Средняя: {statistics.mean(stats['lifespans_female']):.1f} лет")
            output_lines.append(f"      Медиана: {statistics.median(stats['lifespans_female']):.1f} лет")

    # Семьи
    output_lines.append("\n" + "=" * 100)
    output_lines.append("👨‍👩‍👧‍👦 СТАТИСТИКА СЕМЕЙ")
    output_lines.append("=" * 100)

    output_lines.append(f"\n   Всего семей: {stats['total_families']}")
    output_lines.append(f"   Семей с детьми: {stats['families_with_children']}")
    output_lines.append(f"   Семей с датой брака: {stats['families_with_marriage_date']}")

    if stats['children_per_family']:
        output_lines.append(f"\n   Детей в семье:")
        output_lines.append(f"      Среднее: {statistics.mean(stats['children_per_family']):.1f}")
        output_lines.append(f"      Медиана: {statistics.median(stats['children_per_family']):.1f}")
        output_lines.append(f"      Максимум: {max(stats['children_per_family'])}")

        # Распределение
        child_dist = defaultdict(int)
        for n in stats['children_per_family']:
            child_dist[n] += 1

        output_lines.append(f"\n   Распределение по количеству детей:")
        for n in sorted(child_dist.keys())[:10]:
            count = child_dist[n]
            output_lines.append(f"      {n} детей: {count} семей")

    # По десятилетиям
    if args.detailed and stats['births_by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 РОЖДЕНИЯ ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        max_births = max(stats['births_by_decade'].values())
        for decade in sorted(stats['births_by_decade'].keys()):
            count = stats['births_by_decade'][decade]
            bar_len = int(40 * count / max_births) if max_births > 0 else 0
            bar = "█" * bar_len
            output_lines.append(f"   {decade}s: {bar} {count}")

    # Топ мест
    if args.detailed and stats['unique_places']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📍 УНИКАЛЬНЫЕ МЕСТА")
        output_lines.append("=" * 100)

        # Подсчитываем частоту мест
        place_counts = defaultdict(int)
        for person_id, person in data.persons.items():
            if person.birth_place:
                place = person.birth_place.split(',')[0].strip()
                place_counts[place] += 1

        sorted_places = sorted(place_counts.items(), key=lambda x: -x[1])
        output_lines.append(f"\n   Топ-20 мест рождения:")
        for place, count in sorted_places[:20]:
            output_lines.append(f"      {place}: {count}")

    # Вывод
    report = "\n".join(output_lines)
    print(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n💾 Отчёт сохранён в: {args.output}")


if __name__ == '__main__':
    main()
