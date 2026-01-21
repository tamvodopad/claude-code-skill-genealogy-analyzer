#!/usr/bin/env python3
"""
Статистика поколений в генеалогическом древе.
Расчёт интервалов между поколениями, возраста родительства, размера семей.

Использование:
    python3 generation_stats.py tree.ged
    python3 generation_stats.py tree.ged --from @I1@
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Set
from collections import defaultdict
import statistics

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class GenerationData:
    """Данные о поколении."""
    generation: int  # 0 = пробанд, 1 = родители, -1 = дети
    persons: List[Person]
    avg_birth_year: Optional[float]
    year_range: Tuple[int, int]


@dataclass
class ParenthoodStats:
    """Статистика родительства."""
    person: Person
    age_at_first_child: Optional[int]
    age_at_last_child: Optional[int]
    num_children: int
    children_years: List[int]


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def calculate_generation_interval(parent: Person, child: Person) -> Optional[int]:
    """Вычислить интервал между поколениями (возраст родителя при рождении ребёнка)."""
    parent_birth = get_birth_year(parent)
    child_birth = get_birth_year(child)

    if parent_birth and child_birth:
        interval = child_birth - parent_birth
        if 10 <= interval <= 70:  # Реалистичный интервал
            return interval
    return None


def build_generation_tree(data: GedcomData, root_person: Person,
                          max_ancestors: int = 15,
                          max_descendants: int = 10) -> Dict[int, List[Person]]:
    """
    Построение дерева поколений от заданной персоны.
    Положительные значения — предки (1 = родители, 2 = бабушки/дедушки)
    Отрицательные — потомки (-1 = дети, -2 = внуки)
    """
    generations = defaultdict(list)
    generations[0].append(root_person)

    visited_up = {root_person.id}
    visited_down = {root_person.id}

    # Вверх — предки
    def traverse_up(person: Person, gen: int):
        if gen > max_ancestors:
            return

        father, mother = data.get_parents(person)

        if father and father.id not in visited_up:
            visited_up.add(father.id)
            generations[gen].append(father)
            traverse_up(father, gen + 1)

        if mother and mother.id not in visited_up:
            visited_up.add(mother.id)
            generations[gen].append(mother)
            traverse_up(mother, gen + 1)

    # Вниз — потомки
    def traverse_down(person: Person, gen: int):
        if gen < -max_descendants:
            return

        children = data.get_children(person)
        for child in children:
            if child.id not in visited_down:
                visited_down.add(child.id)
                generations[gen].append(child)
                traverse_down(child, gen - 1)

    traverse_up(root_person, 1)
    traverse_down(root_person, -1)

    return dict(generations)


def analyze_generations(generations: Dict[int, List[Person]], data: GedcomData) -> List[GenerationData]:
    """Анализ данных по поколениям."""
    results = []

    for gen_num in sorted(generations.keys(), reverse=True):
        persons = generations[gen_num]

        birth_years = [get_birth_year(p) for p in persons if get_birth_year(p)]

        avg_year = statistics.mean(birth_years) if birth_years else None
        year_range = (min(birth_years), max(birth_years)) if birth_years else (0, 0)

        results.append(GenerationData(
            generation=gen_num,
            persons=persons,
            avg_birth_year=avg_year,
            year_range=year_range
        ))

    return results


def calculate_all_intervals(data: GedcomData, before_year: Optional[int] = None) -> Dict:
    """Расчёт всех интервалов между поколениями."""
    intervals = {
        'father_son': [],
        'father_daughter': [],
        'mother_son': [],
        'mother_daughter': [],
        'all': [],
    }

    for family_id, family in data.families.items():
        father = data.get_person(family.husband_id) if family.husband_id else None
        mother = data.get_person(family.wife_id) if family.wife_id else None

        for child_id in family.children_ids:
            child = data.get_person(child_id)
            if not child:
                continue

            child_birth = get_birth_year(child)
            if before_year and child_birth and child_birth > before_year:
                continue

            if father:
                interval = calculate_generation_interval(father, child)
                if interval:
                    intervals['all'].append(interval)
                    if child.sex == 'M':
                        intervals['father_son'].append(interval)
                    elif child.sex == 'F':
                        intervals['father_daughter'].append(interval)

            if mother:
                interval = calculate_generation_interval(mother, child)
                if interval:
                    intervals['all'].append(interval)
                    if child.sex == 'M':
                        intervals['mother_son'].append(interval)
                    elif child.sex == 'F':
                        intervals['mother_daughter'].append(interval)

    return intervals


def analyze_parenthood(data: GedcomData, before_year: Optional[int] = None) -> Dict:
    """Анализ возраста родительства."""
    stats = {
        'fathers': [],
        'mothers': [],
        'first_child_age_fathers': [],
        'first_child_age_mothers': [],
        'last_child_age_fathers': [],
        'last_child_age_mothers': [],
        'family_sizes': [],
    }

    for family_id, family in data.families.items():
        father = data.get_person(family.husband_id) if family.husband_id else None
        mother = data.get_person(family.wife_id) if family.wife_id else None

        if not family.children_ids:
            continue

        # Получаем года рождения детей
        children_years = []
        for child_id in family.children_ids:
            child = data.get_person(child_id)
            if child:
                year = get_birth_year(child)
                if year:
                    if before_year and year > before_year:
                        continue
                    children_years.append(year)

        if not children_years:
            continue

        children_years.sort()
        first_child_year = min(children_years)
        last_child_year = max(children_years)
        num_children = len(children_years)

        stats['family_sizes'].append(num_children)

        # Отец
        if father:
            father_birth = get_birth_year(father)
            if father_birth:
                first_age = first_child_year - father_birth
                last_age = last_child_year - father_birth

                if 15 <= first_age <= 70:
                    stats['first_child_age_fathers'].append(first_age)
                if 15 <= last_age <= 80:
                    stats['last_child_age_fathers'].append(last_age)

                stats['fathers'].append(ParenthoodStats(
                    person=father,
                    age_at_first_child=first_age if 15 <= first_age <= 70 else None,
                    age_at_last_child=last_age if 15 <= last_age <= 80 else None,
                    num_children=num_children,
                    children_years=children_years
                ))

        # Мать
        if mother:
            mother_birth = get_birth_year(mother)
            if mother_birth:
                first_age = first_child_year - mother_birth
                last_age = last_child_year - mother_birth

                if 12 <= first_age <= 50:
                    stats['first_child_age_mothers'].append(first_age)
                if 12 <= last_age <= 55:
                    stats['last_child_age_mothers'].append(last_age)

                stats['mothers'].append(ParenthoodStats(
                    person=mother,
                    age_at_first_child=first_age if 12 <= first_age <= 50 else None,
                    age_at_last_child=last_age if 12 <= last_age <= 55 else None,
                    num_children=num_children,
                    children_years=children_years
                ))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Статистика поколений в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--from', dest='root', metavar='ID',
                        help='ID начальной персоны (пробанда)')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Анализировать только до указанного года')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("СТАТИСТИКА ПОКОЛЕНИЙ")
    if args.before:
        output_lines.append(f"(до {args.before} года)")
    output_lines.append("=" * 100)

    # Если указана начальная персона — строим дерево
    if args.root:
        root = data.get_person(args.root)
        if not root:
            print(f"Ошибка: персона {args.root} не найдена")
            sys.exit(1)

        output_lines.append(f"\n🌳 ДЕРЕВО ПОКОЛЕНИЙ ДЛЯ: {root.name}")

        generations = build_generation_tree(data, root)
        gen_data = analyze_generations(generations, data)

        gen_names = {
            0: "Пробанд",
            1: "Родители",
            2: "Бабушки/дедушки",
            3: "Прабабушки/прадедушки",
            4: "4-е поколение",
            5: "5-е поколение",
            -1: "Дети",
            -2: "Внуки",
            -3: "Правнуки",
        }

        for gd in gen_data:
            gen_name = gen_names.get(gd.generation, f"{gd.generation}-е поколение")
            year_str = f"~{gd.avg_birth_year:.0f}" if gd.avg_birth_year else "?"
            range_str = f"({gd.year_range[0]}-{gd.year_range[1]})" if gd.year_range[0] else ""

            output_lines.append(f"\n   {gen_name}: {len(gd.persons)} чел., {year_str} {range_str}")

            # Имена (первые 6)
            for p in gd.persons[:6]:
                birth_year = get_birth_year(p) or "?"
                output_lines.append(f"      • {p.name} ({birth_year})")
            if len(gd.persons) > 6:
                output_lines.append(f"      ... и ещё {len(gd.persons) - 6}")

        # Интервалы между соседними поколениями
        output_lines.append("\n" + "-" * 50)
        output_lines.append("ИНТЕРВАЛЫ МЕЖДУ ПОКОЛЕНИЯМИ:")

        for i, gd in enumerate(gen_data):
            if i + 1 < len(gen_data):
                next_gd = gen_data[i + 1]
                if gd.avg_birth_year and next_gd.avg_birth_year:
                    interval = abs(next_gd.avg_birth_year - gd.avg_birth_year)
                    output_lines.append(f"   {gen_names.get(next_gd.generation, str(next_gd.generation))} → "
                                       f"{gen_names.get(gd.generation, str(gd.generation))}: {interval:.1f} лет")

    # Общая статистика интервалов
    intervals = calculate_all_intervals(data, args.before)

    output_lines.append("\n" + "=" * 100)
    output_lines.append("📊 ИНТЕРВАЛЫ МЕЖДУ ПОКОЛЕНИЯМИ (ВСЁ ДРЕВО)")
    output_lines.append("=" * 100)

    if intervals['all']:
        all_int = intervals['all']
        output_lines.append(f"\n   Всего пар родитель-ребёнок: {len(all_int)}")
        output_lines.append(f"   Средний интервал: {statistics.mean(all_int):.1f} лет")
        output_lines.append(f"   Медианный интервал: {statistics.median(all_int):.1f} лет")
        output_lines.append(f"   Минимум: {min(all_int)} лет")
        output_lines.append(f"   Максимум: {max(all_int)} лет")

        # По типам
        type_names = {
            'father_son': 'Отец → сын',
            'father_daughter': 'Отец → дочь',
            'mother_son': 'Мать → сын',
            'mother_daughter': 'Мать → дочь',
        }

        output_lines.append("\n   По типам:")
        for key, name in type_names.items():
            data_list = intervals[key]
            if data_list:
                output_lines.append(f"      {name}: {statistics.mean(data_list):.1f} лет "
                                   f"(n={len(data_list)})")

    # Статистика родительства
    parent_stats = analyze_parenthood(data, args.before)

    output_lines.append("\n" + "=" * 100)
    output_lines.append("👨‍👩‍👧‍👦 ВОЗРАСТ РОДИТЕЛЬСТВА")
    output_lines.append("=" * 100)

    # Первый ребёнок
    if parent_stats['first_child_age_fathers']:
        ages = parent_stats['first_child_age_fathers']
        output_lines.append(f"\n   Отцы при рождении первого ребёнка:")
        output_lines.append(f"      Средний возраст: {statistics.mean(ages):.1f} лет")
        output_lines.append(f"      Медиана: {statistics.median(ages):.1f} лет")
        output_lines.append(f"      Диапазон: {min(ages)}-{max(ages)} лет")

    if parent_stats['first_child_age_mothers']:
        ages = parent_stats['first_child_age_mothers']
        output_lines.append(f"\n   Матери при рождении первого ребёнка:")
        output_lines.append(f"      Средний возраст: {statistics.mean(ages):.1f} лет")
        output_lines.append(f"      Медиана: {statistics.median(ages):.1f} лет")
        output_lines.append(f"      Диапазон: {min(ages)}-{max(ages)} лет")

    # Последний ребёнок
    if parent_stats['last_child_age_mothers']:
        ages = parent_stats['last_child_age_mothers']
        output_lines.append(f"\n   Матери при рождении последнего ребёнка:")
        output_lines.append(f"      Средний возраст: {statistics.mean(ages):.1f} лет")
        output_lines.append(f"      Максимальный: {max(ages)} лет")

    # Размер семей
    if parent_stats['family_sizes']:
        sizes = parent_stats['family_sizes']
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👶 РАЗМЕР СЕМЕЙ (КОЛИЧЕСТВО ДЕТЕЙ)")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   Среднее количество детей: {statistics.mean(sizes):.1f}")
        output_lines.append(f"   Медиана: {statistics.median(sizes):.1f}")
        output_lines.append(f"   Максимум: {max(sizes)}")

        # Распределение
        size_counts = defaultdict(int)
        for s in sizes:
            size_counts[s] += 1

        output_lines.append("\n   Распределение:")
        max_count = max(size_counts.values())
        for size in sorted(size_counts.keys()):
            count = size_counts[size]
            bar_len = int(30 * count / max_count)
            bar = "█" * bar_len
            pct = count / len(sizes) * 100
            output_lines.append(f"      {size:>2} детей: {bar} {count} ({pct:.1f}%)")

        # Многодетные семьи
        large_families = [(p, p.num_children) for p in parent_stats['fathers'] + parent_stats['mothers']
                         if p.num_children >= 8]
        if large_families:
            # Убираем дубликаты по семье
            seen = set()
            unique_large = []
            for p, n in large_families:
                key = tuple(sorted(p.children_years))
                if key not in seen:
                    seen.add(key)
                    unique_large.append((p, n))

            unique_large.sort(key=lambda x: -x[1])

            output_lines.append(f"\n   🏆 Многодетные семьи (8+ детей): {len(unique_large)}")
            for p, n in unique_large[:10]:
                output_lines.append(f"      • {p.person.name}: {n} детей")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Типичные интервалы между поколениями:

   • Крестьянские семьи России (до 1917): 25-30 лет
   • Городские семьи (XX век): 25-30 лет
   • Современность: 28-32 года

   Факторы, влияющие на интервал:
   • Возраст вступления в брак
   • Продолжительность жизни
   • Социальный статус
   • Детская смертность (влияла на количество детей)

   Для генеалогических расчётов обычно используют:
   • 25 лет — стандартный интервал
   • 30 лет — для дворянских семей
   • 20-22 года — для крестьян с ранними браками
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
