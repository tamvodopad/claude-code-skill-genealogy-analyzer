#!/usr/bin/env python3
"""
Анализ сирот и потери родителей в генеалогическом древе.
Возраст потери родителей, влияние на судьбу, паттерны.

Использование:
    python3 orphan_analysis.py tree.ged
    python3 orphan_analysis.py tree.ged --before 1920
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict
from collections import defaultdict
import statistics

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class OrphanData:
    """Данные о сиротстве."""
    person: Person
    birth_year: int
    father: Optional[Person]
    mother: Optional[Person]
    father_death_year: Optional[int]
    mother_death_year: Optional[int]
    age_lost_father: Optional[int]
    age_lost_mother: Optional[int]
    orphan_type: str  # 'full', 'paternal', 'maternal'
    age_became_orphan: Optional[int]


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


def analyze_orphan(person: Person, data: GedcomData, max_orphan_age: int = 18) -> Optional[OrphanData]:
    """Анализ сиротства персоны."""
    birth_year = get_birth_year(person)
    if not birth_year:
        return None

    # Находим родителей
    father = None
    mother = None
    father_death = None
    mother_death = None

    if person.child_family_id:
        family = data.families.get(person.child_family_id)
        if family:
            if family.husband_id:
                father = data.get_person(family.husband_id)
                if father:
                    father_death = get_death_year(father)

            if family.wife_id:
                mother = data.get_person(family.wife_id)
                if mother:
                    mother_death = get_death_year(mother)

    if not father and not mother:
        return None

    # Вычисляем возраст потери родителей
    age_lost_father = None
    age_lost_mother = None

    if father_death and father_death >= birth_year:
        age_lost_father = father_death - birth_year

    if mother_death and mother_death >= birth_year:
        age_lost_mother = mother_death - birth_year

    # Проверяем, был ли сиротой (потерял родителя до max_orphan_age)
    lost_father_young = age_lost_father is not None and age_lost_father <= max_orphan_age
    lost_mother_young = age_lost_mother is not None and age_lost_mother <= max_orphan_age

    if not lost_father_young and not lost_mother_young:
        return None

    # Определяем тип сиротства
    if lost_father_young and lost_mother_young:
        orphan_type = 'full'
        age_became_orphan = min(age_lost_father, age_lost_mother)
    elif lost_father_young:
        orphan_type = 'paternal'
        age_became_orphan = age_lost_father
    else:
        orphan_type = 'maternal'
        age_became_orphan = age_lost_mother

    return OrphanData(
        person=person,
        birth_year=birth_year,
        father=father,
        mother=mother,
        father_death_year=father_death,
        mother_death_year=mother_death,
        age_lost_father=age_lost_father,
        age_lost_mother=age_lost_mother,
        orphan_type=orphan_type,
        age_became_orphan=age_became_orphan
    )


def analyze_all_orphans(data: GedcomData, before_year: Optional[int] = None,
                       max_orphan_age: int = 18) -> Dict:
    """Анализ всех сирот."""
    stats = {
        'total_persons': 0,
        'with_parents_known': 0,
        'orphans': 0,
        'full_orphans': 0,
        'paternal_orphans': 0,  # потеряли отца
        'maternal_orphans': 0,  # потеряли мать
        'cases': [],
        'age_distribution': defaultdict(int),
        'by_decade': defaultdict(lambda: {'total': 0, 'orphans': 0}),
        'by_sex': {'M': {'total': 0, 'orphans': 0}, 'F': {'total': 0, 'orphans': 0}},
        'parent_death_causes': defaultdict(int),  # если известно
        'ages_lost_father': [],
        'ages_lost_mother': [],
    }

    for person_id, person in data.persons.items():
        birth_year = get_birth_year(person)
        if not birth_year:
            continue

        # Фильтр по году
        if before_year and birth_year > before_year:
            continue

        stats['total_persons'] += 1

        # По десятилетиям
        decade = (birth_year // 10) * 10
        stats['by_decade'][decade]['total'] += 1

        # По полу
        if person.sex in ['M', 'F']:
            stats['by_sex'][person.sex]['total'] += 1

        orphan_data = analyze_orphan(person, data, max_orphan_age)
        if not orphan_data:
            continue

        stats['orphans'] += 1
        stats['cases'].append(orphan_data)
        stats['by_decade'][decade]['orphans'] += 1

        if person.sex in ['M', 'F']:
            stats['by_sex'][person.sex]['orphans'] += 1

        # Тип сиротства
        if orphan_data.orphan_type == 'full':
            stats['full_orphans'] += 1
        elif orphan_data.orphan_type == 'paternal':
            stats['paternal_orphans'] += 1
        else:
            stats['maternal_orphans'] += 1

        # Возраст потери родителей
        if orphan_data.age_became_orphan is not None:
            age_bucket = orphan_data.age_became_orphan // 3 * 3  # 0-2, 3-5, 6-8, ...
            stats['age_distribution'][age_bucket] += 1

        if orphan_data.age_lost_father is not None:
            stats['ages_lost_father'].append(orphan_data.age_lost_father)

        if orphan_data.age_lost_mother is not None:
            stats['ages_lost_mother'].append(orphan_data.age_lost_mother)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ сирот и потери родителей'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Анализировать только рождённых до указанного года')
    parser.add_argument('--max-age', type=int, default=18,
                        help='Максимальный возраст для считания сиротой (по умолчанию 18)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ СИРОТ И ПОТЕРИ РОДИТЕЛЕЙ")
    if args.before:
        output_lines.append(f"(рождённые до {args.before} года)")
    output_lines.append(f"(сиротство до {args.max_age} лет)")
    output_lines.append("=" * 100)

    stats = analyze_all_orphans(data, args.before, args.max_age)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего персон с известным годом рождения: {stats['total_persons']}")
    output_lines.append(f"   Потеряли родителя до {args.max_age} лет: {stats['orphans']}")

    if stats['total_persons'] > 0:
        pct = stats['orphans'] / stats['total_persons'] * 100
        output_lines.append(f"   Процент сирот: {pct:.1f}%")

    output_lines.append(f"\n   Типы сиротства:")
    output_lines.append(f"      Полные сироты (оба родителя): {stats['full_orphans']}")
    output_lines.append(f"      Потеряли отца: {stats['paternal_orphans']}")
    output_lines.append(f"      Потеряли мать: {stats['maternal_orphans']}")

    # Возраст потери родителей
    if stats['ages_lost_father'] or stats['ages_lost_mother']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📊 ВОЗРАСТ ПОТЕРИ РОДИТЕЛЕЙ")
        output_lines.append("=" * 100)

        if stats['ages_lost_father']:
            avg = statistics.mean(stats['ages_lost_father'])
            med = statistics.median(stats['ages_lost_father'])
            output_lines.append(f"\n   Потеря отца:")
            output_lines.append(f"      Средний возраст: {avg:.1f} лет")
            output_lines.append(f"      Медиана: {med:.1f} лет")
            output_lines.append(f"      Диапазон: {min(stats['ages_lost_father'])}-{max(stats['ages_lost_father'])} лет")

        if stats['ages_lost_mother']:
            avg = statistics.mean(stats['ages_lost_mother'])
            med = statistics.median(stats['ages_lost_mother'])
            output_lines.append(f"\n   Потеря матери:")
            output_lines.append(f"      Средний возраст: {avg:.1f} лет")
            output_lines.append(f"      Медиана: {med:.1f} лет")
            output_lines.append(f"      Диапазон: {min(stats['ages_lost_mother'])}-{max(stats['ages_lost_mother'])} лет")

    # Распределение по возрасту
    if stats['age_distribution']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📈 РАСПРЕДЕЛЕНИЕ ПО ВОЗРАСТУ ОСИРОТЕНИЯ")
        output_lines.append("=" * 100)

        max_count = max(stats['age_distribution'].values())
        for age_bucket in sorted(stats['age_distribution'].keys()):
            count = stats['age_distribution'][age_bucket]
            bar_len = int(30 * count / max_count) if max_count > 0 else 0
            bar = "█" * bar_len
            pct = count / stats['orphans'] * 100 if stats['orphans'] > 0 else 0
            output_lines.append(f"   {age_bucket:>2}-{age_bucket+2:<2} лет: {bar} {count} ({pct:.1f}%)")

    # По десятилетиям
    if stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 СИРОТСТВО ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   {'Период':<12} {'Всего':<10} {'Сирот':<10} {'%':<10}")
        output_lines.append("   " + "-" * 45)

        for decade in sorted(stats['by_decade'].keys()):
            d = stats['by_decade'][decade]
            if d['total'] > 0:
                pct = d['orphans'] / d['total'] * 100
                output_lines.append(f"   {decade}s       {d['total']:<10} {d['orphans']:<10} {pct:.1f}%")

    # По полу
    output_lines.append("\n" + "=" * 100)
    output_lines.append("👫 СИРОТСТВО ПО ПОЛУ")
    output_lines.append("=" * 100)

    for sex, label in [('M', 'Мужчины'), ('F', 'Женщины')]:
        d = stats['by_sex'][sex]
        if d['total'] > 0:
            pct = d['orphans'] / d['total'] * 100
            output_lines.append(f"\n   {label}:")
            output_lines.append(f"      Всего: {d['total']}")
            output_lines.append(f"      Сирот: {d['orphans']} ({pct:.1f}%)")

    # Детальные случаи
    if stats['cases']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📋 ПРИМЕРЫ СИРОТСТВА")
        output_lines.append("=" * 100)

        # Сначала полные сироты
        full_orphans = [c for c in stats['cases'] if c.orphan_type == 'full']
        if full_orphans:
            output_lines.append(f"\n   Полные сироты ({len(full_orphans)}):")
            for orphan in sorted(full_orphans, key=lambda x: x.age_became_orphan or 99)[:10]:
                age_f = f"отец †{orphan.age_lost_father}л" if orphan.age_lost_father is not None else ""
                age_m = f"мать †{orphan.age_lost_mother}л" if orphan.age_lost_mother is not None else ""
                output_lines.append(f"      {orphan.person.name} ({orphan.birth_year}): {age_f}, {age_m}")

        # Младенцы без отца
        infant_paternal = [c for c in stats['cases']
                         if c.orphan_type == 'paternal' and c.age_lost_father is not None and c.age_lost_father <= 1]
        if infant_paternal:
            output_lines.append(f"\n   Потеряли отца в младенчестве (до 1 года): {len(infant_paternal)}")
            for orphan in infant_paternal[:5]:
                father_name = orphan.father.name if orphan.father else "?"
                output_lines.append(f"      {orphan.person.name} — отец: {father_name} (†{orphan.father_death_year})")

        # Потеряли мать при родах (возраст 0)
        lost_mother_birth = [c for c in stats['cases']
                           if c.age_lost_mother is not None and c.age_lost_mother == 0]
        if lost_mother_birth:
            output_lines.append(f"\n   Возможно потеряли мать при родах: {len(lost_mother_birth)}")
            for orphan in lost_mother_birth[:5]:
                mother_name = orphan.mother.name if orphan.mother else "?"
                output_lines.append(f"      {orphan.person.name} ({orphan.birth_year}) — мать: {mother_name}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Сиротство в исторической перспективе:

   📊 Частота сиротства (до XX века):
   • Потеря отца до 18 лет: 20-30%
   • Потеря матери до 18 лет: 15-25%
   • Полное сиротство: 5-10%

   ⚰️ Причины смерти родителей:
   • Матери — часто при родах или от послеродовых осложнений
   • Отцы — болезни, несчастные случаи, войны
   • Оба — эпидемии (холера, тиф, грипп)

   👨‍👩‍👧 Последствия сиротства:
   • Часто — воспитание родственниками (бабушки, тёти)
   • Мачеха/отчим — повторные браки были частыми
   • Ранний труд и ответственность
   • Возможно — худшие шансы на образование, брак

   📈 Изменения во времени:
   • XIX век — высокая детская смертность, много сирот
   • XX век — снижение смертности, меньше сирот
   • Войны — всплески патернального сиротства

   ⚠️ Ограничения:
   • Даты смерти родителей часто неизвестны
   • Реальный процент сирот был выше
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
