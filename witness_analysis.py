#!/usr/bin/env python3
"""
Анализ свидетелей на свадьбах и крещениях в генеалогическом древе.
Поручители, восприемники, социальные связи.

Использование:
    python3 witness_analysis.py tree.ged
    python3 witness_analysis.py tree.ged --person @I1@
    python3 witness_analysis.py tree.ged --event marriage
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
class WitnessRecord:
    """Запись о свидетеле."""
    witness_name: str
    witness_id: Optional[str]  # если свидетель есть в дереве
    witness_person: Optional[Person]
    event_type: str  # 'marriage', 'baptism'
    event_year: Optional[int]
    principal_person: Person  # кого крестили / кто женился
    principal_family: Optional[Family]  # для браков
    role: str  # 'поручитель', 'восприемник', 'свидетель'
    is_relative: bool
    relationship: Optional[str]


@dataclass
class WitnessStats:
    """Статистика свидетеля."""
    name: str
    person_id: Optional[str]
    person: Optional[Person]
    times_witness: int = 0
    marriages_witnessed: List = field(default_factory=list)
    baptisms_witnessed: List = field(default_factory=list)
    relatives_witnessed: int = 0
    non_relatives_witnessed: int = 0


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def find_witnesses_in_notes(notes: str, data: GedcomData) -> List[Tuple[str, str, Optional[str]]]:
    """Найти свидетелей в заметках."""
    witnesses = []

    if not notes:
        return witnesses

    notes_lower = notes.lower()

    # Паттерны для поиска свидетелей
    patterns = [
        # Поручители на свадьбе
        (r'поручител[ьи][:\s]+([^.;]+)', 'поручитель'),
        (r'свидетел[ьи][:\s]+([^.;]+)', 'свидетель'),
        (r'по жених[еу][:\s]+([^.;]+)', 'поручитель жениха'),
        (r'по невест[еы][:\s]+([^.;]+)', 'поручитель невесты'),
        # Восприемники на крещении
        (r'восприемник[и]?[:\s]+([^.;]+)', 'восприемник'),
        (r'крёстн[ыйая][еи]?[:\s]+([^.;]+)', 'крёстный'),
    ]

    for pattern, role in patterns:
        matches = re.findall(pattern, notes_lower)
        for match in matches:
            # Разделяем если несколько имён
            names = re.split(r',|и\s+', match)
            for name in names:
                name = name.strip()
                if len(name) > 2:
                    witnesses.append((name, role, None))

    return witnesses


def find_witnesses_from_associations(person: Person, data: GedcomData) -> List[Tuple[str, str, Optional[str]]]:
    """Найти свидетелей из ASSO записей."""
    witnesses = []

    if not hasattr(person, 'associations') or not person.associations:
        return witnesses

    for assoc in person.associations:
        if not hasattr(assoc, 'relation') or not assoc.relation:
            continue

        rel = assoc.relation.lower()

        # Типы связей свидетелей
        witness_roles = {
            'witness': 'свидетель',
            'свидетель': 'свидетель',
            'поручитель': 'поручитель',
            'восприемник': 'восприемник',
            'godfather': 'крёстный отец',
            'godmother': 'крёстная мать',
            'godparent': 'крёстный',
        }

        for key, role in witness_roles.items():
            if key in rel:
                assoc_id = getattr(assoc, 'person_id', None)
                assoc_person = data.get_person(assoc_id) if assoc_id else None
                name = assoc_person.name if assoc_person else assoc_id
                witnesses.append((name, role, assoc_id))
                break

    return witnesses


def is_relative(person1: Person, person2: Person, data: GedcomData) -> Tuple[bool, Optional[str]]:
    """Проверить родство между персонами."""
    if not person1 or not person2:
        return False, None

    # Сиблинги
    if person1.child_family_id and person2.child_family_id:
        if person1.child_family_id == person2.child_family_id:
            return True, "брат/сестра"

    # Родитель-ребёнок
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

    # Супруги
    for fam_id in (person1.spouse_family_ids or []):
        family = data.families.get(fam_id)
        if family:
            if family.husband_id == person2.id or family.wife_id == person2.id:
                return True, "супруг(а)"

    # Дядя/тётя - племянник
    # Проверяем родителей person1
    if person1.child_family_id:
        p1_family = data.families.get(person1.child_family_id)
        if p1_family:
            for parent_id in [p1_family.husband_id, p1_family.wife_id]:
                if not parent_id:
                    continue
                parent = data.get_person(parent_id)
                if parent and parent.child_family_id:
                    grandparent_family = data.families.get(parent.child_family_id)
                    if grandparent_family:
                        # Сиблинги родителя = дяди/тёти
                        for child_id in grandparent_family.children_ids:
                            if child_id == parent_id:
                                continue
                            if child_id == person2.id:
                                return True, "дядя/тётя"

    return False, None


def analyze_witnesses(data: GedcomData, event_filter: str = None) -> Dict:
    """Анализ свидетелей."""
    stats = {
        'total_events': 0,
        'events_with_witnesses': 0,
        'total_witness_records': 0,
        'witness_records': [],
        'witness_stats': {},  # witness_name -> WitnessStats
        'by_decade': defaultdict(lambda: {'marriages': 0, 'baptisms': 0, 'witnesses': 0}),
        'relative_witnesses': 0,
        'non_relative_witnesses': 0,
        'top_witnesses': [],
        'witness_pairs': defaultdict(int),  # пары свидетелей, которые часто выступают вместе
    }

    # Анализ браков
    if not event_filter or event_filter == 'marriage':
        for family_id, family in data.families.items():
            if not family.marriage_date and not family.marriage_year:
                continue

            stats['total_events'] += 1
            year = family.marriage_date.year if family.marriage_date else family.marriage_year
            decade = (year // 10) * 10 if year else None

            if decade:
                stats['by_decade'][decade]['marriages'] += 1

            husband = data.get_person(family.husband_id) if family.husband_id else None
            wife = data.get_person(family.wife_id) if family.wife_id else None

            witnesses_found = []

            # Ищем свидетелей в заметках семьи
            if hasattr(family, 'notes') and family.notes:
                notes = family.notes if isinstance(family.notes, str) else ' '.join(family.notes)
                witnesses_found.extend(find_witnesses_in_notes(notes, data))

            # Ищем в ассоциациях мужа и жены
            if husband:
                witnesses_found.extend(find_witnesses_from_associations(husband, data))
            if wife:
                witnesses_found.extend(find_witnesses_from_associations(wife, data))

            if witnesses_found:
                stats['events_with_witnesses'] += 1

                if decade:
                    stats['by_decade'][decade]['witnesses'] += len(witnesses_found)

                witness_names_in_event = []

                for witness_name, role, witness_id in witnesses_found:
                    stats['total_witness_records'] += 1

                    witness_person = data.get_person(witness_id) if witness_id else None
                    principal = husband or wife

                    is_rel, rel_type = False, None
                    if witness_person and principal:
                        is_rel, rel_type = is_relative(witness_person, principal, data)

                    if is_rel:
                        stats['relative_witnesses'] += 1
                    else:
                        stats['non_relative_witnesses'] += 1

                    record = WitnessRecord(
                        witness_name=witness_name,
                        witness_id=witness_id,
                        witness_person=witness_person,
                        event_type='marriage',
                        event_year=year,
                        principal_person=principal,
                        principal_family=family,
                        role=role,
                        is_relative=is_rel,
                        relationship=rel_type
                    )
                    stats['witness_records'].append(record)

                    # Обновляем статистику свидетеля
                    key = witness_id or witness_name.lower()
                    if key not in stats['witness_stats']:
                        stats['witness_stats'][key] = WitnessStats(
                            name=witness_name,
                            person_id=witness_id,
                            person=witness_person
                        )
                    ws = stats['witness_stats'][key]
                    ws.times_witness += 1
                    ws.marriages_witnessed.append(record)
                    if is_rel:
                        ws.relatives_witnessed += 1
                    else:
                        ws.non_relatives_witnessed += 1

                    witness_names_in_event.append(key)

                # Пары свидетелей
                for i, w1 in enumerate(witness_names_in_event):
                    for w2 in witness_names_in_event[i+1:]:
                        pair = tuple(sorted([w1, w2]))
                        stats['witness_pairs'][pair] += 1

    # Анализ крещений (через ассоциации персон)
    if not event_filter or event_filter == 'baptism':
        for person_id, person in data.persons.items():
            birth_year = get_birth_year(person)

            witnesses_found = find_witnesses_from_associations(person, data)

            # Фильтруем только крёстных/восприемников
            baptism_witnesses = [(n, r, i) for n, r, i in witnesses_found
                                if 'крёстн' in r or 'восприемник' in r or 'godfather' in r.lower() or 'godmother' in r.lower()]

            if baptism_witnesses:
                stats['total_events'] += 1
                stats['events_with_witnesses'] += 1

                decade = (birth_year // 10) * 10 if birth_year else None
                if decade:
                    stats['by_decade'][decade]['baptisms'] += 1
                    stats['by_decade'][decade]['witnesses'] += len(baptism_witnesses)

                for witness_name, role, witness_id in baptism_witnesses:
                    stats['total_witness_records'] += 1

                    witness_person = data.get_person(witness_id) if witness_id else None

                    is_rel, rel_type = False, None
                    if witness_person:
                        is_rel, rel_type = is_relative(witness_person, person, data)

                    if is_rel:
                        stats['relative_witnesses'] += 1
                    else:
                        stats['non_relative_witnesses'] += 1

                    record = WitnessRecord(
                        witness_name=witness_name,
                        witness_id=witness_id,
                        witness_person=witness_person,
                        event_type='baptism',
                        event_year=birth_year,
                        principal_person=person,
                        principal_family=None,
                        role=role,
                        is_relative=is_rel,
                        relationship=rel_type
                    )
                    stats['witness_records'].append(record)

                    # Обновляем статистику
                    key = witness_id or witness_name.lower()
                    if key not in stats['witness_stats']:
                        stats['witness_stats'][key] = WitnessStats(
                            name=witness_name,
                            person_id=witness_id,
                            person=witness_person
                        )
                    ws = stats['witness_stats'][key]
                    ws.times_witness += 1
                    ws.baptisms_witnessed.append(record)
                    if is_rel:
                        ws.relatives_witnessed += 1
                    else:
                        ws.non_relatives_witnessed += 1

    # Топ свидетелей
    sorted_witnesses = sorted(stats['witness_stats'].values(),
                             key=lambda x: -x.times_witness)
    stats['top_witnesses'] = sorted_witnesses[:30]

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ свидетелей на свадьбах и крещениях'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--person', metavar='ID',
                        help='Анализ для конкретной персоны')
    parser.add_argument('--event', choices=['marriage', 'baptism'],
                        help='Фильтр по типу события')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ СВИДЕТЕЛЕЙ (ПОРУЧИТЕЛЕЙ, ВОСПРИЕМНИКОВ)")
    output_lines.append("=" * 100)

    stats = analyze_witnesses(data, args.event)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Событий с датами: {stats['total_events']}")
    output_lines.append(f"   Событий со свидетелями: {stats['events_with_witnesses']}")
    output_lines.append(f"   Всего записей о свидетелях: {stats['total_witness_records']}")
    output_lines.append(f"   Уникальных свидетелей: {len(stats['witness_stats'])}")

    if stats['total_witness_records'] > 0:
        rel_pct = stats['relative_witnesses'] / stats['total_witness_records'] * 100
        output_lines.append(f"\n   Свидетели-родственники: {stats['relative_witnesses']} ({rel_pct:.1f}%)")
        output_lines.append(f"   Свидетели не родственники: {stats['non_relative_witnesses']}")

    # Анализ конкретной персоны
    if args.person:
        person = data.get_person(args.person)
        if person:
            output_lines.append("\n" + "=" * 100)
            output_lines.append(f"🔍 АНАЛИЗ ПЕРСОНЫ: {person.name}")
            output_lines.append("=" * 100)

            # Где эта персона была свидетелем
            as_witness = [r for r in stats['witness_records']
                         if r.witness_id == args.person]
            if as_witness:
                output_lines.append(f"\n   Был(а) свидетелем {len(as_witness)} раз:")
                for r in as_witness[:15]:
                    event_str = "браке" if r.event_type == 'marriage' else "крещении"
                    rel_str = f" ({r.relationship})" if r.is_relative else ""
                    output_lines.append(f"      • На {event_str} {r.principal_person.name} ({r.event_year}){rel_str}")

            # Свидетели на событиях этой персоны
            principal_records = [r for r in stats['witness_records']
                                if r.principal_person and r.principal_person.id == args.person]
            if principal_records:
                output_lines.append(f"\n   Свидетели на событиях {person.name}:")
                for r in principal_records:
                    event_str = "браке" if r.event_type == 'marriage' else "крещении"
                    rel_str = f" ({r.relationship})" if r.is_relative else ""
                    output_lines.append(f"      • {r.witness_name} на {event_str} ({r.role}){rel_str}")
        else:
            output_lines.append(f"\n   ⚠️ Персона {args.person} не найдена")

    # Топ свидетелей
    if stats['top_witnesses']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🏆 ТОП СВИДЕТЕЛЕЙ (больше всего событий)")
        output_lines.append("=" * 100)

        for ws in stats['top_witnesses'][:20]:
            marriages = len(ws.marriages_witnessed)
            baptisms = len(ws.baptisms_witnessed)
            rel_str = f", из них родственники: {ws.relatives_witnessed}" if ws.relatives_witnessed > 0 else ""

            output_lines.append(f"\n   {ws.name}: {ws.times_witness} событий")
            output_lines.append(f"      Браков: {marriages}, Крещений: {baptisms}{rel_str}")

            # Примеры
            examples = (ws.marriages_witnessed + ws.baptisms_witnessed)[:3]
            for r in examples:
                event_str = "брак" if r.event_type == 'marriage' else "крещение"
                output_lines.append(f"      • {event_str} {r.principal_person.name} ({r.event_year})")

    # Частые пары свидетелей
    if stats['witness_pairs']:
        frequent_pairs = [(pair, count) for pair, count in stats['witness_pairs'].items()
                         if count >= 2]
        if frequent_pairs:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("👥 ЧАСТЫЕ ПАРЫ СВИДЕТЕЛЕЙ")
            output_lines.append("=" * 100)

            sorted_pairs = sorted(frequent_pairs, key=lambda x: -x[1])[:15]

            for pair, count in sorted_pairs:
                w1 = stats['witness_stats'].get(pair[0])
                w2 = stats['witness_stats'].get(pair[1])
                name1 = w1.name if w1 else pair[0]
                name2 = w2.name if w2 else pair[1]
                output_lines.append(f"   {name1} + {name2}: {count} совместных событий")

    # По десятилетиям
    if stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        for decade in sorted(stats['by_decade'].keys()):
            d = stats['by_decade'][decade]
            output_lines.append(f"   {decade}s: браков {d['marriages']}, крещений {d['baptisms']}, свидетелей {d['witnesses']}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Свидетели в православных обрядах России:

   💒 ПОРУЧИТЕЛИ НА СВАДЬБЕ:
   • Обычно 2-4 человека (по 1-2 с каждой стороны)
   • Часто родственники (братья, дяди, кузены)
   • Иногда уважаемые члены общины
   • Должны быть православными и совершеннолетними
   • Не могли быть крёстными жениха/невесты (духовное родство)

   ⛪ ВОСПРИЕМНИКИ (КРЁСТНЫЕ):
   • Крёстный отец и крёстная мать обязательны
   • Становились духовными родственниками
   • Не могли вступать в брак с крестником
   • Часто выбирали из родственников или друзей
   • Важная социальная связь (кумовство)

   🔍 ЧТО МОЖНО УЗНАТЬ:
   • Социальные связи семьи
   • Уровень благосостояния (знатные свидетели)
   • Географические связи (свидетели из других мест)
   • Семейные традиции (повторяющиеся свидетели)

   📋 ЗАПИСИ В GEDCOM:
   • ASSO с RELA witness/поручитель — свидетели на свадьбе
   • ASSO с RELA godparent/godfather/godmother — крёстные
   • Часто информация в NOTE

   ⚠️ ОГРАНИЧЕНИЯ:
   • Не все программы записывают свидетелей
   • Данные могут быть неполными
   • Имена свидетелей не всегда идентифицированы в дереве
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
