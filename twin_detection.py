#!/usr/bin/env python3
"""
Поиск близнецов в генеалогическом древе.
Детекция по датам рождения, именам, паттернам.

Использование:
    python3 twin_detection.py tree.ged
    python3 twin_detection.py tree.ged --max-days 7
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class TwinPair:
    """Пара близнецов."""
    person1: Person
    person2: Person
    family: Family
    birth_date1: Optional[date]
    birth_date2: Optional[date]
    days_apart: int
    same_sex: bool
    confidence: str  # 'high', 'medium', 'low'
    notes: List[str]


def get_birth_date(person: Person) -> Optional[date]:
    """Получить полную дату рождения."""
    if person.birth_date:
        if hasattr(person.birth_date, 'year') and hasattr(person.birth_date, 'month') and hasattr(person.birth_date, 'day'):
            if person.birth_date.year and person.birth_date.month and person.birth_date.day:
                return date(person.birth_date.year, person.birth_date.month, person.birth_date.day)
    return None


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def get_given_name(person: Person) -> str:
    """Получить имя."""
    if hasattr(person, 'given_name') and person.given_name:
        return person.given_name
    if person.name:
        parts = person.name.replace('/', '').split()
        if parts:
            return parts[0]
    return ""


def find_twins_in_family(family: Family, data: GedcomData, max_days: int = 7) -> List[TwinPair]:
    """Найти близнецов в семье."""
    twins = []

    children = []
    for child_id in family.children_ids:
        child = data.get_person(child_id)
        if child:
            children.append(child)

    if len(children) < 2:
        return twins

    # Сортируем по дате рождения
    def sort_key(p):
        bd = get_birth_date(p)
        if bd:
            return bd
        by = get_birth_year(p)
        if by:
            return date(by, 6, 15)  # середина года
        return date(9999, 1, 1)

    children.sort(key=sort_key)

    # Проверяем пары последовательных детей
    for i in range(len(children) - 1):
        child1 = children[i]
        child2 = children[i + 1]

        bd1 = get_birth_date(child1)
        bd2 = get_birth_date(child2)

        by1 = get_birth_year(child1)
        by2 = get_birth_year(child2)

        days_apart = None
        confidence = 'low'
        notes = []

        # Если есть полные даты
        if bd1 and bd2:
            days_apart = abs((bd2 - bd1).days)
            if days_apart <= max_days:
                if days_apart == 0:
                    confidence = 'high'
                    notes.append("Одна дата рождения")
                elif days_apart <= 1:
                    confidence = 'high'
                    notes.append(f"Разница {days_apart} день")
                elif days_apart <= 3:
                    confidence = 'medium'
                    notes.append(f"Разница {days_apart} дня")
                else:
                    confidence = 'low'
                    notes.append(f"Разница {days_apart} дней (возможно)")
            else:
                continue  # Не близнецы
        # Если только годы
        elif by1 and by2 and by1 == by2:
            # Проверяем дополнительные признаки
            days_apart = 0
            confidence = 'low'
            notes.append("Один год рождения (нет точных дат)")

            # Повышаем уверенность если одинаковый пол
            if child1.sex == child2.sex:
                notes.append("Одинаковый пол")

            # Проверяем, нет ли между ними других детей
            other_children_same_year = sum(1 for c in children
                if c != child1 and c != child2 and get_birth_year(c) == by1)
            if other_children_same_year == 0:
                notes.append("Нет других детей того же года")
                confidence = 'medium'
        else:
            continue

        same_sex = child1.sex == child2.sex if child1.sex and child2.sex else False

        twin_pair = TwinPair(
            person1=child1,
            person2=child2,
            family=family,
            birth_date1=bd1,
            birth_date2=bd2,
            days_apart=days_apart,
            same_sex=same_sex,
            confidence=confidence,
            notes=notes
        )
        twins.append(twin_pair)

    # Проверяем тройни и более
    if len(children) >= 3:
        for i in range(len(children) - 2):
            bd1 = get_birth_date(children[i])
            bd3 = get_birth_date(children[i + 2])

            if bd1 and bd3:
                total_days = abs((bd3 - bd1).days)
                if total_days <= max_days:
                    # Возможно тройня
                    for twin in twins:
                        if twin.person1 == children[i] or twin.person2 == children[i]:
                            twin.notes.append("⚠️ Возможна тройня!")

    return twins


def analyze_all_twins(data: GedcomData, max_days: int = 7) -> Dict:
    """Анализ всех близнецов."""
    stats = {
        'total_families': 0,
        'families_with_twins': 0,
        'total_twin_pairs': 0,
        'identical_possible': 0,  # однояйцевые (одного пола)
        'fraternal_possible': 0,   # разнояйцевые (разного пола)
        'high_confidence': [],
        'medium_confidence': [],
        'low_confidence': [],
        'by_decade': defaultdict(int),
        'twin_mortality': {'died_both': 0, 'died_one': 0, 'survived_both': 0, 'unknown': 0}
    }

    for family_id, family in data.families.items():
        stats['total_families'] += 1

        twins = find_twins_in_family(family, data, max_days)

        if twins:
            stats['families_with_twins'] += 1
            stats['total_twin_pairs'] += len(twins)

            for twin in twins:
                if twin.same_sex:
                    stats['identical_possible'] += 1
                else:
                    stats['fraternal_possible'] += 1

                if twin.confidence == 'high':
                    stats['high_confidence'].append(twin)
                elif twin.confidence == 'medium':
                    stats['medium_confidence'].append(twin)
                else:
                    stats['low_confidence'].append(twin)

                # По десятилетиям
                by1 = get_birth_year(twin.person1)
                if by1:
                    decade = (by1 // 10) * 10
                    stats['by_decade'][decade] += 1

                # Анализ смертности близнецов
                died1 = twin.person1.death_date is not None or twin.person1.death_year is not None
                died2 = twin.person2.death_date is not None or twin.person2.death_year is not None

                # Проверяем детскую смертность
                dy1 = twin.person1.death_date.year if twin.person1.death_date else twin.person1.death_year
                dy2 = twin.person2.death_date.year if twin.person2.death_date else twin.person2.death_year
                by1 = get_birth_year(twin.person1)
                by2 = get_birth_year(twin.person2)

                infant_death1 = dy1 and by1 and (dy1 - by1) <= 5
                infant_death2 = dy2 and by2 and (dy2 - by2) <= 5

                if infant_death1 and infant_death2:
                    stats['twin_mortality']['died_both'] += 1
                elif infant_death1 or infant_death2:
                    stats['twin_mortality']['died_one'] += 1
                elif died1 or died2:
                    # Умерли, но не в детстве
                    stats['twin_mortality']['survived_both'] += 1
                else:
                    stats['twin_mortality']['unknown'] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Поиск близнецов в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--max-days', type=int, default=7,
                        help='Максимальная разница в днях для близнецов (по умолчанию 7)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("ПОИСК БЛИЗНЕЦОВ")
    output_lines.append(f"(максимальная разница в датах: {args.max_days} дней)")
    output_lines.append("=" * 100)

    stats = analyze_all_twins(data, args.max_days)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего семей: {stats['total_families']}")
    output_lines.append(f"   Семей с близнецами: {stats['families_with_twins']}")
    output_lines.append(f"   Всего пар близнецов: {stats['total_twin_pairs']}")

    if stats['total_families'] > 0:
        pct = stats['families_with_twins'] / stats['total_families'] * 100
        output_lines.append(f"   Процент семей с близнецами: {pct:.2f}%")

    output_lines.append(f"\n   Возможно однояйцевые (одного пола): {stats['identical_possible']}")
    output_lines.append(f"   Возможно разнояйцевые (разного пола): {stats['fraternal_possible']}")

    # Высокая уверенность
    if stats['high_confidence']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👶👶 БЛИЗНЕЦЫ (высокая уверенность)")
        output_lines.append("=" * 100)

        for twin in stats['high_confidence']:
            sex_type = "однополые" if twin.same_sex else "разнополые"
            bd1_str = twin.birth_date1.isoformat() if twin.birth_date1 else "?"
            bd2_str = twin.birth_date2.isoformat() if twin.birth_date2 else "?"

            output_lines.append(f"\n   👶 {twin.person1.name}")
            output_lines.append(f"   👶 {twin.person2.name}")
            output_lines.append(f"      Даты: {bd1_str} / {bd2_str}")
            output_lines.append(f"      Тип: {sex_type}")
            output_lines.append(f"      Признаки: {', '.join(twin.notes)}")

            # Родители
            father = data.get_person(twin.family.husband_id) if twin.family.husband_id else None
            mother = data.get_person(twin.family.wife_id) if twin.family.wife_id else None
            parents = []
            if father:
                parents.append(f"отец: {father.name}")
            if mother:
                parents.append(f"мать: {mother.name}")
            if parents:
                output_lines.append(f"      Родители: {', '.join(parents)}")

    # Средняя уверенность
    if stats['medium_confidence']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👶👶 ВЕРОЯТНЫЕ БЛИЗНЕЦЫ (средняя уверенность)")
        output_lines.append("=" * 100)

        for twin in stats['medium_confidence'][:20]:
            sex_type = "однополые" if twin.same_sex else "разнополые"
            by1 = get_birth_year(twin.person1)
            by2 = get_birth_year(twin.person2)

            output_lines.append(f"\n   👶 {twin.person1.name} ({by1 or '?'})")
            output_lines.append(f"   👶 {twin.person2.name} ({by2 or '?'})")
            output_lines.append(f"      Тип: {sex_type}")
            output_lines.append(f"      Признаки: {', '.join(twin.notes)}")

        if len(stats['medium_confidence']) > 20:
            output_lines.append(f"\n   ... и ещё {len(stats['medium_confidence']) - 20} пар")

    # Низкая уверенность
    if stats['low_confidence']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("❓ ВОЗМОЖНЫЕ БЛИЗНЕЦЫ (низкая уверенность)")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   Найдено {len(stats['low_confidence'])} пар")
        output_lines.append("   (дети одного года рождения без точных дат)")

        for twin in stats['low_confidence'][:10]:
            by = get_birth_year(twin.person1)
            output_lines.append(f"\n   • {twin.person1.name} + {twin.person2.name} ({by or '?'})")

    # Смертность близнецов
    mortality = stats['twin_mortality']
    total_known = mortality['died_both'] + mortality['died_one'] + mortality['survived_both']
    if total_known > 0:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("⚰️ СМЕРТНОСТЬ БЛИЗНЕЦОВ В ДЕТСТВЕ")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   Умерли оба в детстве (<5 лет): {mortality['died_both']}")
        output_lines.append(f"   Умер один из близнецов: {mortality['died_one']}")
        output_lines.append(f"   Оба пережили детство: {mortality['survived_both']}")
        output_lines.append(f"   Нет данных: {mortality['unknown']}")

    # По десятилетиям
    if stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 БЛИЗНЕЦЫ ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        for decade in sorted(stats['by_decade'].keys()):
            count = stats['by_decade'][decade]
            output_lines.append(f"   {decade}s: {count}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Частота близнецов:

   • Естественная частота: ~1-2% от всех родов
   • Однояйцевые (идентичные): ~0.3-0.4%
   • Разнояйцевые (дизиготные): ~0.7-1.5%

   Факторы риска близнецов:
   • Возраст матери >35 лет
   • Наследственность по материнской линии
   • Многодетность

   Смертность близнецов (исторически):
   • Выше, чем у одиночных детей
   • Особенно высока при недоношенности
   • Один из близнецов часто умирал вскоре после рождения

   Типы близнецов:
   • Однополые — могут быть как идентичными, так и дизиготными
   • Разнополые — всегда дизиготные

   ⚠️ Ограничения детекции:
   • Без точных дат — только предположения
   • Близнецы могли умереть и не быть записаны
   • Требуется проверка по первоисточникам
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
