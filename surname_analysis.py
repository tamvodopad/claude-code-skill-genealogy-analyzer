#!/usr/bin/env python3
"""
Анализ фамилий в генеалогическом древе.
Распределение, происхождение, изменения фамилий.

Использование:
    python3 surname_analysis.py tree.ged
    python3 surname_analysis.py tree.ged --surname Попов
    python3 surname_analysis.py tree.ged --etymology
"""

import sys
import argparse
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Set, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


# Паттерны для определения происхождения фамилий
SURNAME_PATTERNS = {
    'patronymic': {
        'patterns': [r'.*ов$', r'.*ев$', r'.*ин$', r'.*ын$'],
        'description': 'От имени отца (патронимическая)',
        'examples': 'Иванов, Петров, Ильин'
    },
    'occupational': {
        'patterns': [r'.*ник$', r'.*чик$', r'.*щик$', r'.*арь$', r'.*ач$'],
        'description': 'От профессии (профессиональная)',
        'examples': 'Кузнецов, Ткачёв, Гончаров'
    },
    'geographical': {
        'patterns': [r'.*ский$', r'.*цкий$', r'.*ской$'],
        'description': 'От места (географическая)',
        'examples': 'Московский, Донской, Тверской'
    },
    'nickname': {
        'patterns': [r'.*ый$', r'.*ой$', r'.*ко$'],
        'description': 'От прозвища (прозвищная)',
        'examples': 'Белый, Долгий, Шевченко'
    },
}

# Известные профессиональные фамилии
OCCUPATIONAL_SURNAMES = {
    'Кузнецов': 'кузнец',
    'Мельников': 'мельник',
    'Ткачёв': 'ткач',
    'Ткачев': 'ткач',
    'Гончаров': 'гончар',
    'Плотников': 'плотник',
    'Столяров': 'столяр',
    'Рыбаков': 'рыбак',
    'Пастухов': 'пастух',
    'Овчинников': 'овчинник',
    'Сапожников': 'сапожник',
    'Бондаренко': 'бондарь',
    'Коваль': 'кузнец (укр.)',
    'Ковальчук': 'сын кузнеца',
    'Шевченко': 'швец/портной',
    'Мельниченко': 'сын мельника',
    'Бочаров': 'бочар',
    'Винокуров': 'винокур',
    'Звонарёв': 'звонарь',
    'Пономарёв': 'пономарь',
    'Дьяконов': 'дьякон',
    'Попов': 'поп/священник',
}


@dataclass
class SurnameData:
    """Данные о фамилии."""
    surname: str
    count: int
    persons: List[Person]
    origin_type: str
    origin_description: str
    first_appearance: Optional[int]  # год
    places: List[str]


def normalize_surname(surname: str) -> str:
    """Нормализация фамилии."""
    if not surname:
        return ""

    s = surname.strip()
    # Убираем ё -> е для сравнения
    s_norm = s.lower().replace('ё', 'е')
    return s_norm


def get_surname(person: Person) -> Optional[str]:
    """Получить фамилию персоны."""
    if person.surname:
        return person.surname.strip()

    # Попробуем извлечь из полного имени
    if person.name:
        # GEDCOM формат: имя /фамилия/
        import re
        match = re.search(r'/([^/]+)/', person.name)
        if match:
            surname = match.group(1).strip()
            if surname:
                return surname

        # Fallback: последнее слово, если оно похоже на фамилию
        parts = person.name.split()
        if len(parts) >= 2:
            # Фамилии обычно заканчиваются на -ов/-ев/-ин/-ая/-ова/-ева
            last = parts[-1]
            if re.search(r'(ов|ев|ёв|ин|ын|ая|ова|ева|ина|ский|ская|цкий|цкая)$', last, re.IGNORECASE):
                return last

    return None


def detect_surname_origin(surname: str) -> Tuple[str, str]:
    """Определение происхождения фамилии."""
    if not surname:
        return 'unknown', 'Не определено'

    s_lower = normalize_surname(surname)

    # Проверяем известные профессиональные
    if surname in OCCUPATIONAL_SURNAMES:
        return 'occupational', f"От профессии: {OCCUPATIONAL_SURNAMES[surname]}"

    # Проверяем паттерны
    for origin_type, data in SURNAME_PATTERNS.items():
        for pattern in data['patterns']:
            if re.match(pattern, s_lower):
                return origin_type, data['description']

    return 'unknown', 'Происхождение не определено'


def analyze_surnames(data: GedcomData) -> Dict[str, SurnameData]:
    """Анализ всех фамилий."""
    surnames = defaultdict(lambda: {
        'count': 0,
        'persons': [],
        'places': set(),
        'years': []
    })

    for person_id, person in data.persons.items():
        surname = get_surname(person)
        if not surname:
            continue

        surname_norm = normalize_surname(surname)
        surnames[surname_norm]['count'] += 1
        surnames[surname_norm]['persons'].append(person)
        surnames[surname_norm]['original'] = surname  # Сохраняем оригинальное написание

        # Места
        if person.birth_place:
            place = person.birth_place.split(',')[0].strip()
            surnames[surname_norm]['places'].add(place)

        # Годы
        birth_year = person.birth_date.year if person.birth_date else person.birth_year
        if birth_year:
            surnames[surname_norm]['years'].append(birth_year)

    # Конвертируем в SurnameData
    results = {}
    for surname_norm, data_dict in surnames.items():
        origin_type, origin_desc = detect_surname_origin(data_dict.get('original', surname_norm))

        first_year = min(data_dict['years']) if data_dict['years'] else None

        results[surname_norm] = SurnameData(
            surname=data_dict.get('original', surname_norm),
            count=data_dict['count'],
            persons=data_dict['persons'],
            origin_type=origin_type,
            origin_description=origin_desc,
            first_appearance=first_year,
            places=list(data_dict['places'])
        )

    return results


def trace_surname_line(data: GedcomData, surname: str, max_gen: int = 15) -> List[Dict]:
    """Отслеживание линии фамилии (по мужской линии)."""
    surname_norm = normalize_surname(surname)
    line = []

    # Находим всех с этой фамилией
    persons_with_surname = []
    for person_id, person in data.persons.items():
        if normalize_surname(get_surname(person) or '') == surname_norm:
            persons_with_surname.append(person)

    if not persons_with_surname:
        return line

    # Строим дерево по мужской линии
    def find_male_line_ancestors(person: Person, gen: int, visited: Set[str]) -> List[Dict]:
        if gen > max_gen or person.id in visited:
            return []

        visited.add(person.id)
        result = [{
            'person': person,
            'generation': gen,
            'surname': get_surname(person)
        }]

        father, _ = data.get_parents(person)
        if father:
            result.extend(find_male_line_ancestors(father, gen + 1, visited))

        return result

    # Для каждой персоны строим линию предков
    all_lines = []
    for person in persons_with_surname:
        visited = set()
        line = find_male_line_ancestors(person, 0, visited)
        if len(line) > 1:
            all_lines.append(line)

    # Находим самую длинную линию
    if all_lines:
        return max(all_lines, key=len)

    return []


def analyze_surname_changes(data: GedcomData) -> List[Dict]:
    """Анализ изменений фамилий (женщины при замужестве)."""
    changes = []

    for family_id, family in data.families.items():
        wife = data.get_person(family.wife_id) if family.wife_id else None
        husband = data.get_person(family.husband_id) if family.husband_id else None

        if not wife or not husband:
            continue

        wife_surname = get_surname(wife)
        husband_surname = get_surname(husband)

        if wife_surname and husband_surname:
            # Проверяем, взяла ли жена фамилию мужа
            if normalize_surname(wife_surname) == normalize_surname(husband_surname):
                # Возможно, родовая фамилия
                # Ищем её родителей
                father, mother = data.get_parents(wife)
                maiden_surname = None
                if father:
                    maiden_surname = get_surname(father)
                elif mother:
                    maiden_surname = get_surname(mother)

                if maiden_surname and normalize_surname(maiden_surname) != normalize_surname(wife_surname):
                    changes.append({
                        'person': wife,
                        'maiden_name': maiden_surname,
                        'married_name': wife_surname,
                        'husband': husband,
                        'year': family.marriage_year or (family.marriage_date.year if family.marriage_date else None)
                    })

    return changes


def main():
    parser = argparse.ArgumentParser(
        description='Анализ фамилий в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--surname', metavar='NAME',
                        help='Детальный анализ конкретной фамилии')
    parser.add_argument('--etymology', action='store_true',
                        help='Показать этимологию фамилий')
    parser.add_argument('--top', type=int, default=30, metavar='N',
                        help='Топ N фамилий')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    gedcom_data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(gedcom_data.persons)} персон, {len(gedcom_data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ФАМИЛИЙ")
    output_lines.append("=" * 100)

    # Анализ всех фамилий
    surnames = analyze_surnames(gedcom_data)

    if args.surname:
        # Детальный анализ конкретной фамилии
        surname_norm = normalize_surname(args.surname)

        if surname_norm not in surnames:
            output_lines.append(f"\n⚠️ Фамилия '{args.surname}' не найдена в древе")
            # Поиск похожих
            similar = [s for s in surnames.keys() if surname_norm[:3] in s]
            if similar:
                output_lines.append(f"   Похожие фамилии: {', '.join([surnames[s].surname for s in similar[:5]])}")
        else:
            sd = surnames[surname_norm]
            output_lines.append(f"\n📛 ФАМИЛИЯ: {sd.surname}")
            output_lines.append(f"\n   Количество носителей: {sd.count}")
            output_lines.append(f"   Происхождение: {sd.origin_description}")

            if sd.first_appearance:
                output_lines.append(f"   Первое упоминание: {sd.first_appearance} год")

            if sd.places:
                output_lines.append(f"\n   📍 География:")
                for place in sd.places[:10]:
                    output_lines.append(f"      • {place}")

            # Носители фамилии
            output_lines.append(f"\n   👤 Носители:")
            # Сортируем по году рождения
            sorted_persons = sorted(sd.persons,
                                    key=lambda p: p.birth_date.year if p.birth_date else (p.birth_year or 9999))
            for person in sorted_persons[:15]:
                birth_year = person.birth_date.year if person.birth_date else person.birth_year
                year_str = f"({birth_year})" if birth_year else ""
                output_lines.append(f"      • {person.name} {year_str}")

            if len(sd.persons) > 15:
                output_lines.append(f"      ... и ещё {len(sd.persons) - 15}")

            # Линия фамилии
            line = trace_surname_line(gedcom_data, args.surname)
            if line:
                output_lines.append(f"\n   🌳 МУЖСКАЯ ЛИНИЯ (от самого раннего к позднему):")
                for item in reversed(line):
                    birth_year = item['person'].birth_date.year if item['person'].birth_date else item['person'].birth_year
                    year_str = f"({birth_year})" if birth_year else ""
                    output_lines.append(f"      {'  ' * item['generation']}└─ {item['person'].name} {year_str}")

    else:
        # Общий анализ
        output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
        output_lines.append(f"   Уникальных фамилий: {len(surnames)}")

        total_with_surname = sum(sd.count for sd in surnames.values())
        output_lines.append(f"   Персон с фамилиями: {total_with_surname}")

        # Топ фамилий
        sorted_surnames = sorted(surnames.values(), key=lambda x: -x.count)

        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"🏆 ТОП-{args.top} ФАМИЛИЙ")
        output_lines.append("=" * 100)

        for i, sd in enumerate(sorted_surnames[:args.top], 1):
            first_year = f", с {sd.first_appearance}" if sd.first_appearance else ""
            origin = f" [{sd.origin_type}]" if args.etymology else ""
            output_lines.append(f"   {i:>2}. {sd.surname:<20} — {sd.count:>3} чел.{first_year}{origin}")

        # По происхождению (если запрошена этимология)
        if args.etymology:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("📚 ФАМИЛИИ ПО ПРОИСХОЖДЕНИЮ")
            output_lines.append("=" * 100)

            by_origin = defaultdict(list)
            for sd in surnames.values():
                by_origin[sd.origin_type].append(sd)

            origin_names = {
                'patronymic': '👨 От имени отца (патронимические)',
                'occupational': '🔨 От профессии',
                'geographical': '🗺️ От места (географические)',
                'nickname': '📝 От прозвища',
                'unknown': '❓ Происхождение не определено'
            }

            for origin_type, items in by_origin.items():
                output_lines.append(f"\n{origin_names.get(origin_type, origin_type)}:")
                # Топ-10 в каждой категории
                sorted_items = sorted(items, key=lambda x: -x.count)
                for sd in sorted_items[:10]:
                    output_lines.append(f"   {sd.surname}: {sd.count} чел.")
                if len(items) > 10:
                    output_lines.append(f"   ... и ещё {len(items) - 10}")

        # Редкие фамилии (1-2 носителя)
        rare = [sd for sd in surnames.values() if sd.count <= 2]
        if rare:
            output_lines.append("\n" + "=" * 100)
            output_lines.append(f"💎 РЕДКИЕ ФАМИЛИИ (1-2 носителя): {len(rare)}")
            output_lines.append("=" * 100)

            for sd in sorted(rare, key=lambda x: x.surname)[:30]:
                output_lines.append(f"   {sd.surname}")

            if len(rare) > 30:
                output_lines.append(f"   ... и ещё {len(rare) - 30}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 СПРАВКА О РУССКИХ ФАМИЛИЯХ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Типы происхождения фамилий:

   1. ПАТРОНИМИЧЕСКИЕ (от имени отца) — самые распространённые
      • -ов/-ев: Иванов, Петров, Алексеев
      • -ин/-ын: Ильин, Фомин, Кузьмин

   2. ПРОФЕССИОНАЛЬНЫЕ (от занятия предка)
      • Кузнецов, Мельников, Ткачёв, Рыбаков

   3. ГЕОГРАФИЧЕСКИЕ (от места происхождения)
      • -ский/-цкий: Московский, Полтавский
      • Часто указывают на дворянское происхождение

   4. ПРОЗВИЩНЫЕ (от внешности, характера)
      • Белов, Чернов, Толстой, Кривой

   Исторические факты:
   • Крестьяне получали фамилии массово после 1861 года
   • До этого фамилии имели дворяне, купцы, мещане
   • Многие крестьянские фамилии — от имени помещика или деревни
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
