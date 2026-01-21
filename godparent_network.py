#!/usr/bin/env python3
"""
Анализ сети крёстных родителей в генеалогическом древе.
Связи через кумовство, социальные сети, паттерны выбора крёстных.

Использование:
    python3 godparent_network.py tree.ged
    python3 godparent_network.py tree.ged --person @I1@
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Set, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class GodparentRelation:
    """Связь крёстный-крестник."""
    godparent: Person
    godchild: Person
    godparent_type: str  # 'godfather', 'godmother'
    year: Optional[int]
    is_relative: bool
    relationship: Optional[str]  # если родственник


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def find_godparents(person: Person, data: GedcomData) -> List[Tuple[Person, str]]:
    """Найти крёстных персоны."""
    godparents = []

    # В GEDCOM крёстные записываются через ASSO с RELA godparent/godfather/godmother
    if hasattr(person, 'associations') and person.associations:
        for assoc in person.associations:
            if hasattr(assoc, 'relation') and assoc.relation:
                rel = assoc.relation.lower()
                if 'godfather' in rel or 'крёстн' in rel and 'отец' in rel:
                    gp = data.get_person(assoc.person_id) if hasattr(assoc, 'person_id') else None
                    if gp:
                        godparents.append((gp, 'godfather'))
                elif 'godmother' in rel or 'крёстн' in rel and 'мать' in rel:
                    gp = data.get_person(assoc.person_id) if hasattr(assoc, 'person_id') else None
                    if gp:
                        godparents.append((gp, 'godmother'))
                elif 'godparent' in rel or 'крёстн' in rel:
                    gp = data.get_person(assoc.person_id) if hasattr(assoc, 'person_id') else None
                    if gp:
                        gp_type = 'godfather' if gp.sex == 'M' else 'godmother'
                        godparents.append((gp, gp_type))

    # Также проверяем notes на упоминания крёстных
    if hasattr(person, 'notes') and person.notes:
        notes = person.notes if isinstance(person.notes, list) else [person.notes]
        for note in notes:
            if note and 'крёстн' in note.lower():
                # Пытаемся извлечь имена (простой паттерн)
                pass  # Сложный парсинг, оставляем для будущего

    return godparents


def find_godchildren(person: Person, data: GedcomData) -> List[Person]:
    """Найти крестников персоны."""
    godchildren = []

    for person_id, p in data.persons.items():
        godparents = find_godparents(p, data)
        for gp, gp_type in godparents:
            if gp and gp.id == person.id:
                godchildren.append(p)

    return godchildren


def is_relative(person1: Person, person2: Person, data: GedcomData) -> Tuple[bool, Optional[str]]:
    """Проверить, являются ли персоны родственниками."""
    # Простая проверка — одна семья
    if person1.child_family_id and person2.child_family_id:
        if person1.child_family_id == person2.child_family_id:
            return True, "сиблинги"

    # Проверяем родителей
    if person1.child_family_id:
        family = data.families.get(person1.child_family_id)
        if family:
            if family.husband_id == person2.id:
                return True, "отец"
            if family.wife_id == person2.id:
                return True, "мать"

    if person2.child_family_id:
        family = data.families.get(person2.child_family_id)
        if family:
            if family.husband_id == person1.id:
                return True, "ребёнок"
            if family.wife_id == person1.id:
                return True, "ребёнок"

    # Проверяем супругов
    for fam_id in (person1.spouse_family_ids or []):
        family = data.families.get(fam_id)
        if family:
            if family.husband_id == person2.id or family.wife_id == person2.id:
                return True, "супруг(а)"

    return False, None


def analyze_godparent_network(data: GedcomData) -> Dict:
    """Анализ сети крёстных."""
    stats = {
        'total_persons': 0,
        'with_godparents': 0,
        'total_relations': 0,
        'relations': [],
        'godparents_count': defaultdict(int),  # сколько крестников у каждого
        'godchildren_count': defaultdict(int),  # сколько крёстных у каждого
        'relative_godparents': 0,
        'non_relative_godparents': 0,
        'by_decade': defaultdict(lambda: {'total': 0, 'relative': 0}),
        'top_godparents': [],
        'network_clusters': [],
    }

    all_godparents = set()
    all_godchildren = set()

    for person_id, person in data.persons.items():
        stats['total_persons'] += 1

        godparents = find_godparents(person, data)
        if not godparents:
            continue

        stats['with_godparents'] += 1
        birth_year = get_birth_year(person)
        decade = (birth_year // 10) * 10 if birth_year else None

        for godparent, gp_type in godparents:
            stats['total_relations'] += 1

            is_rel, rel_type = is_relative(godparent, person, data)

            relation = GodparentRelation(
                godparent=godparent,
                godchild=person,
                godparent_type=gp_type,
                year=birth_year,
                is_relative=is_rel,
                relationship=rel_type
            )
            stats['relations'].append(relation)

            stats['godparents_count'][godparent.id] += 1
            stats['godchildren_count'][person.id] += 1

            all_godparents.add(godparent.id)
            all_godchildren.add(person.id)

            if is_rel:
                stats['relative_godparents'] += 1
            else:
                stats['non_relative_godparents'] += 1

            if decade:
                stats['by_decade'][decade]['total'] += 1
                if is_rel:
                    stats['by_decade'][decade]['relative'] += 1

    # Топ крёстных (больше всего крестников)
    top_gp = sorted(stats['godparents_count'].items(), key=lambda x: -x[1])
    for gp_id, count in top_gp[:20]:
        gp = data.get_person(gp_id)
        if gp:
            stats['top_godparents'].append((gp, count))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ сети крёстных родителей'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--person', metavar='ID',
                        help='Детальный анализ для конкретной персоны')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ СЕТИ КРЁСТНЫХ РОДИТЕЛЕЙ")
    output_lines.append("=" * 100)

    stats = analyze_godparent_network(data)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего персон: {stats['total_persons']}")
    output_lines.append(f"   С известными крёстными: {stats['with_godparents']}")
    output_lines.append(f"   Всего связей крёстный-крестник: {stats['total_relations']}")

    if stats['total_relations'] > 0:
        rel_pct = stats['relative_godparents'] / stats['total_relations'] * 100
        non_rel_pct = stats['non_relative_godparents'] / stats['total_relations'] * 100
        output_lines.append(f"\n   Крёстные-родственники: {stats['relative_godparents']} ({rel_pct:.1f}%)")
        output_lines.append(f"   Крёстные не родственники: {stats['non_relative_godparents']} ({non_rel_pct:.1f}%)")

    # Анализ конкретной персоны
    if args.person:
        person = data.get_person(args.person)
        if person:
            output_lines.append("\n" + "=" * 100)
            output_lines.append(f"🔍 АНАЛИЗ ПЕРСОНЫ: {person.name}")
            output_lines.append("=" * 100)

            godparents = find_godparents(person, data)
            if godparents:
                output_lines.append(f"\n   Крёстные {person.name}:")
                for gp, gp_type in godparents:
                    type_str = "крёстный отец" if gp_type == 'godfather' else "крёстная мать"
                    is_rel, rel_type = is_relative(gp, person, data)
                    rel_str = f" ({rel_type})" if is_rel else ""
                    output_lines.append(f"      {type_str}: {gp.name}{rel_str}")

            godchildren = find_godchildren(person, data)
            if godchildren:
                output_lines.append(f"\n   Крестники {person.name} ({len(godchildren)}):")
                for gc in godchildren[:20]:
                    by = get_birth_year(gc)
                    output_lines.append(f"      • {gc.name} ({by or '?'})")
        else:
            output_lines.append(f"\n   ⚠️ Персона {args.person} не найдена")

    # Топ крёстных
    if stats['top_godparents']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👨‍👩‍👧 ТОП КРЁСТНЫХ (больше всего крестников)")
        output_lines.append("=" * 100)

        for gp, count in stats['top_godparents']:
            output_lines.append(f"\n   {gp.name}: {count} крестников")

            # Показываем крестников
            godchildren = [r for r in stats['relations'] if r.godparent.id == gp.id]
            for rel in godchildren[:5]:
                by = get_birth_year(rel.godchild)
                rel_str = f" ({rel.relationship})" if rel.is_relative else ""
                output_lines.append(f"      • {rel.godchild.name} ({by or '?'}){rel_str}")
            if len(godchildren) > 5:
                output_lines.append(f"      ... и ещё {len(godchildren) - 5}")

    # По десятилетиям
    if stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 КРЁСТНЫЕ ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        for decade in sorted(stats['by_decade'].keys()):
            d = stats['by_decade'][decade]
            if d['total'] > 0:
                rel_pct = d['relative'] / d['total'] * 100
                output_lines.append(f"   {decade}s: {d['total']} связей ({rel_pct:.1f}% родственники)")

    # Детальные связи
    if stats['relations']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📋 ВСЕ СВЯЗИ КРЁСТНЫЙ-КРЕСТНИК")
        output_lines.append("=" * 100)

        # Группируем по десятилетиям
        by_decade = defaultdict(list)
        for rel in stats['relations']:
            decade = (rel.year // 10) * 10 if rel.year else None
            by_decade[decade].append(rel)

        for decade in sorted(by_decade.keys()):
            if decade:
                output_lines.append(f"\n   {decade}s:")
            else:
                output_lines.append(f"\n   Без даты:")

            for rel in by_decade[decade][:10]:
                gp_type = "⬆️" if rel.godparent_type == 'godfather' else "⬇️"
                rel_str = f" [{rel.relationship}]" if rel.is_relative else ""
                output_lines.append(f"      {gp_type} {rel.godparent.name} → {rel.godchild.name}{rel_str}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Традиции крещения в православной России:

   👨‍👩‍👧 Роль крёстных:
   • Духовные родители ребёнка
   • Обязанность наставлять в вере
   • Помощь семье в воспитании
   • В случае сиротства — забота о крестнике

   👥 Выбор крёстных:
   • Родственники (дяди, тёти, дедушки)
   • Уважаемые члены общины
   • Соседи, друзья семьи
   • Иногда — люди высокого статуса (покровительство)

   ⛔ Ограничения:
   • Родители не могли быть крёстными своих детей
   • Супруги не могли быть крёстными одного ребёнка
   • Крёстные не могли вступать в брак между собой

   🔗 Социальные связи:
   • Кумовство — важная социальная связь
   • Крёстные часто помогали крестникам
   • Сеть крёстных = социальный капитал семьи

   ⚠️ В GEDCOM крёстные записываются через ASSO с RELA godparent.
   Многие программы не поддерживают эту запись.
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
