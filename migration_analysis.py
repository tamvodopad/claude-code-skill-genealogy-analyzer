#!/usr/bin/env python3
"""
Анализ географической миграции в генеалогическом древе.
Отслеживает перемещения семей между населёнными пунктами по поколениям.

Использование:
    python3 migration_analysis.py tree.ged
    python3 migration_analysis.py tree.ged --person @I1@
    python3 migration_analysis.py tree.ged --show-map
"""

import sys
import argparse
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class LocationEvent:
    """Событие с локацией."""
    person: Person
    event_type: str  # birth, death, residence, marriage
    place: str
    year: Optional[int]
    normalized_place: str


@dataclass
class MigrationEvent:
    """Событие миграции."""
    person: Person
    from_place: str
    to_place: str
    year_from: Optional[int]
    year_to: Optional[int]
    event_type: str  # birth_to_death, birth_to_marriage, residence_change


@dataclass
class FamilyMigrationPattern:
    """Паттерн миграции семьи."""
    family: Family
    origin_places: List[str]  # места рождения предков
    destination_place: str     # место жительства семьи
    distance_generations: int  # через сколько поколений


def normalize_place(place: str) -> str:
    """Нормализация названия места для сравнения."""
    if not place:
        return ""

    # Приводим к нижнему регистру
    p = place.lower().strip()

    # Убираем типичные сокращения и уточнения
    remove_patterns = [
        r'\s*губ\.?\s*',
        r'\s*уезд\.?\s*',
        r'\s*волость\.?\s*',
        r'\s*обл\.?\s*',
        r'\s*область\s*',
        r'\s*район\s*',
        r'\s*р-н\.?\s*',
        r'\s*село\s*',
        r'\s*с\.\s*',
        r'\s*деревня\s*',
        r'\s*д\.\s*',
        r'\s*город\s*',
        r'\s*г\.\s*',
        r'\s*посёлок\s*',
        r'\s*п\.\s*',
        r'\s*ст\.\s*',
        r'\s*станица\s*',
    ]

    for pattern in remove_patterns:
        p = re.sub(pattern, ' ', p, flags=re.IGNORECASE)

    # Убираем лишние пробелы
    p = ' '.join(p.split())

    return p


def extract_main_place(place: str) -> str:
    """Извлечение основного населённого пункта (первая часть)."""
    if not place:
        return ""

    # Берём первую часть до запятой
    parts = place.split(',')
    if parts:
        return parts[0].strip()
    return place.strip()


def extract_region(place: str) -> str:
    """Извлечение региона (губернии, области)."""
    if not place:
        return ""

    # Ищем губернию или область
    patterns = [
        r'(\w+)\s+губ\.?',
        r'(\w+)\s+губерния',
        r'(\w+)\s+обл\.?',
        r'(\w+)\s+область',
    ]

    for pattern in patterns:
        match = re.search(pattern, place, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Последняя часть после запятой
    parts = place.split(',')
    if len(parts) > 1:
        return parts[-1].strip()

    return ""


def get_person_locations(person: Person, data: GedcomData) -> List[LocationEvent]:
    """Получить все локации персоны."""
    locations = []

    # Рождение
    if person.birth_place:
        year = person.birth_date.year if person.birth_date else person.birth_year
        locations.append(LocationEvent(
            person=person,
            event_type='birth',
            place=person.birth_place,
            year=year,
            normalized_place=normalize_place(person.birth_place)
        ))

    # Смерть
    if person.death_place:
        year = person.death_date.year if person.death_date else person.death_year
        locations.append(LocationEvent(
            person=person,
            event_type='death',
            place=person.death_place,
            year=year,
            normalized_place=normalize_place(person.death_place)
        ))

    # Резиденции (если есть)
    for residence in getattr(person, 'residences', []):
        if residence.get('place'):
            locations.append(LocationEvent(
                person=person,
                event_type='residence',
                place=residence['place'],
                year=residence.get('year'),
                normalized_place=normalize_place(residence['place'])
            ))

    # Браки
    for spouse in data.get_spouses(person):
        # Находим семью
        for fam_id in person.spouse_family_ids:
            family = data.families.get(fam_id)
            if family and family.marriage_place:
                year = family.marriage_date.year if family.marriage_date else family.marriage_year
                locations.append(LocationEvent(
                    person=person,
                    event_type='marriage',
                    place=family.marriage_place,
                    year=year,
                    normalized_place=normalize_place(family.marriage_place)
                ))

    return sorted(locations, key=lambda x: x.year or 9999)


def find_person_migrations(person: Person, data: GedcomData) -> List[MigrationEvent]:
    """Найти миграции персоны."""
    migrations = []
    locations = get_person_locations(person, data)

    if len(locations) < 2:
        return migrations

    # Сравниваем последовательные локации
    for i in range(len(locations) - 1):
        loc1 = locations[i]
        loc2 = locations[i + 1]

        # Сравниваем основные места
        place1 = extract_main_place(loc1.place)
        place2 = extract_main_place(loc2.place)

        if place1.lower() != place2.lower() and place1 and place2:
            migrations.append(MigrationEvent(
                person=person,
                from_place=loc1.place,
                to_place=loc2.place,
                year_from=loc1.year,
                year_to=loc2.year,
                event_type=f"{loc1.event_type}_to_{loc2.event_type}"
            ))

    return migrations


def analyze_all_migrations(data: GedcomData) -> Dict:
    """Анализ миграций всего древа."""
    stats = {
        'total_persons': len(data.persons),
        'persons_with_places': 0,
        'persons_with_migrations': 0,
        'total_migrations': 0,
        'migrations': [],
        'by_place': defaultdict(lambda: {'births': 0, 'deaths': 0, 'arrivals': 0, 'departures': 0}),
        'by_region': defaultdict(lambda: {'births': 0, 'deaths': 0}),
        'migration_routes': defaultdict(int),  # (from, to) -> count
        'by_decade': defaultdict(int),
    }

    for person_id, person in data.persons.items():
        has_place = False

        # Место рождения
        if person.birth_place:
            has_place = True
            main_place = extract_main_place(person.birth_place)
            region = extract_region(person.birth_place)
            stats['by_place'][main_place]['births'] += 1
            if region:
                stats['by_region'][region]['births'] += 1

        # Место смерти
        if person.death_place:
            has_place = True
            main_place = extract_main_place(person.death_place)
            region = extract_region(person.death_place)
            stats['by_place'][main_place]['deaths'] += 1
            if region:
                stats['by_region'][region]['deaths'] += 1

        if has_place:
            stats['persons_with_places'] += 1

        # Миграции
        migrations = find_person_migrations(person, data)
        if migrations:
            stats['persons_with_migrations'] += 1
            stats['total_migrations'] += len(migrations)
            stats['migrations'].extend(migrations)

            for mig in migrations:
                from_main = extract_main_place(mig.from_place)
                to_main = extract_main_place(mig.to_place)

                stats['by_place'][from_main]['departures'] += 1
                stats['by_place'][to_main]['arrivals'] += 1

                route = (from_main, to_main)
                stats['migration_routes'][route] += 1

                if mig.year_to:
                    decade = (mig.year_to // 10) * 10
                    stats['by_decade'][decade] += 1

    return stats


def analyze_family_origins(data: GedcomData, person: Person, max_gen: int = 5) -> Dict:
    """Анализ географического происхождения семьи."""
    origins = {
        'person': person,
        'ancestors_by_place': defaultdict(list),
        'generations': {},
    }

    def traverse(p: Person, gen: int, line: str):
        if gen > max_gen:
            return

        if p.birth_place:
            main_place = extract_main_place(p.birth_place)
            origins['ancestors_by_place'][main_place].append({
                'person': p,
                'generation': gen,
                'line': line
            })

            if gen not in origins['generations']:
                origins['generations'][gen] = []
            origins['generations'][gen].append({
                'person': p,
                'place': main_place,
                'line': line
            })

        father, mother = data.get_parents(p)
        if father:
            traverse(father, gen + 1, line + 'F')
        if mother:
            traverse(mother, gen + 1, line + 'M')

    traverse(person, 0, '')
    return origins


def main():
    parser = argparse.ArgumentParser(
        description='Анализ географической миграции в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--person', metavar='ID',
                        help='ID персоны для анализа происхождения')
    parser.add_argument('--max-gen', type=int, default=5, metavar='N',
                        help='Глубина анализа предков (по умолчанию: 5)')
    parser.add_argument('--top', type=int, default=20, metavar='N',
                        help='Топ N мест для отображения')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ГЕОГРАФИЧЕСКОЙ МИГРАЦИИ")
    output_lines.append("=" * 100)

    if args.person:
        # Анализ происхождения конкретной персоны
        person = data.get_person(args.person)
        if not person:
            print(f"Ошибка: персона {args.person} не найдена")
            sys.exit(1)

        output_lines.append(f"\n🌍 ГЕОГРАФИЧЕСКОЕ ПРОИСХОЖДЕНИЕ: {person.name}")

        origins = analyze_family_origins(data, person, args.max_gen)

        # По поколениям
        output_lines.append("\n📊 МЕСТА РОЖДЕНИЯ ПО ПОКОЛЕНИЯМ:")
        gen_names = {0: 'Сам', 1: 'Родители', 2: 'Бабушки/дедушки',
                     3: 'Прабабушки/прадедушки', 4: '4-е поколение', 5: '5-е поколение'}

        for gen in sorted(origins['generations'].keys()):
            gen_data = origins['generations'][gen]
            places = defaultdict(list)
            for item in gen_data:
                places[item['place']].append(item['person'].name)

            output_lines.append(f"\n   {gen_names.get(gen, f'{gen}-е поколение')}:")
            for place, persons in places.items():
                output_lines.append(f"      📍 {place}: {', '.join(persons)}")

        # Основные места
        output_lines.append("\n🏠 ОСНОВНЫЕ МЕСТА ПРОИСХОЖДЕНИЯ:")
        sorted_places = sorted(origins['ancestors_by_place'].items(),
                               key=lambda x: -len(x[1]))
        for place, ancestors in sorted_places[:10]:
            output_lines.append(f"   {place}: {len(ancestors)} предков")
            for anc in ancestors[:3]:
                gen_str = gen_names.get(anc['generation'], f"{anc['generation']}-е пок.")
                output_lines.append(f"      • {anc['person'].name} ({gen_str})")

        # Миграции этой персоны
        migrations = find_person_migrations(person, data)
        if migrations:
            output_lines.append(f"\n🚶 ПЕРЕМЕЩЕНИЯ {person.given_name or person.name}:")
            for mig in migrations:
                year_str = ""
                if mig.year_from and mig.year_to:
                    year_str = f" ({mig.year_from} → {mig.year_to})"
                elif mig.year_to:
                    year_str = f" (до {mig.year_to})"
                output_lines.append(f"   {mig.from_place} → {mig.to_place}{year_str}")

    else:
        # Общий анализ
        stats = analyze_all_migrations(data)

        output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
        output_lines.append(f"   Персон с указанием мест: {stats['persons_with_places']} из {stats['total_persons']}")
        output_lines.append(f"   Персон с миграциями: {stats['persons_with_migrations']}")
        output_lines.append(f"   Всего миграций: {stats['total_migrations']}")

        # Топ мест
        if stats['by_place']:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("🏘️ ТОП НАСЕЛЁННЫХ ПУНКТОВ")
            output_lines.append("=" * 100)

            sorted_places = sorted(stats['by_place'].items(),
                                   key=lambda x: -(x[1]['births'] + x[1]['deaths']))

            output_lines.append(f"\n{'Место':<40} {'Рожд.':<8} {'Смерт.':<8} {'Прибыл':<8} {'Убыл':<8}")
            output_lines.append("-" * 80)

            for place, counts in sorted_places[:args.top]:
                if not place:
                    continue
                place_short = place[:38] + '..' if len(place) > 40 else place
                output_lines.append(f"{place_short:<40} {counts['births']:<8} {counts['deaths']:<8} "
                                   f"{counts['arrivals']:<8} {counts['departures']:<8}")

        # Регионы
        if stats['by_region']:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("🗺️ СТАТИСТИКА ПО РЕГИОНАМ (ГУБЕРНИЯМ)")
            output_lines.append("=" * 100)

            sorted_regions = sorted(stats['by_region'].items(),
                                    key=lambda x: -(x[1]['births'] + x[1]['deaths']))

            for region, counts in sorted_regions[:15]:
                if not region:
                    continue
                output_lines.append(f"   {region}: {counts['births']} рождений, {counts['deaths']} смертей")

        # Популярные маршруты миграции
        if stats['migration_routes']:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("🚶 ПОПУЛЯРНЫЕ МАРШРУТЫ МИГРАЦИИ")
            output_lines.append("=" * 100)

            sorted_routes = sorted(stats['migration_routes'].items(), key=lambda x: -x[1])

            for (from_place, to_place), count in sorted_routes[:15]:
                if count > 1:
                    output_lines.append(f"   {from_place} → {to_place}: {count} человек")

        # Миграции по десятилетиям
        if stats['by_decade']:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("📅 МИГРАЦИИ ПО ДЕСЯТИЛЕТИЯМ")
            output_lines.append("=" * 100)

            max_count = max(stats['by_decade'].values()) if stats['by_decade'] else 1
            for decade in sorted(stats['by_decade'].keys()):
                count = stats['by_decade'][decade]
                bar_len = int(40 * count / max_count)
                bar = "█" * bar_len
                output_lines.append(f"   {decade}s: {bar} {count}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Анализ миграции помогает понять:

   • Географическое происхождение семьи
   • Паттерны переселения (город ↔ деревня, между губерниями)
   • Влияние исторических событий (войны, голод, индустриализация)
   • Связь с профессиональной деятельностью (ремесленники, торговцы)

   Типичные паттерны в России:
   • До 1861 — крепостные крестьяне привязаны к месту
   • 1861-1917 — рост миграции в города
   • 1917-1930 — урбанизация и коллективизация
   • После 1930 — индустриализация, массовый переезд в города
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
