#!/usr/bin/env python3
"""
Анализ «кирпичных стен» (тупиков) в генеалогическом древе.
Находит конечных предков и анализирует глубину линий.

Использование:
    python3 brick_walls.py tree.ged
    python3 brick_walls.py tree.ged --from @I1@  # от конкретной персоны
"""

import sys
import argparse
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, GedcomData


@dataclass
class BrickWall:
    """Кирпичная стена — конечный предок без известных родителей."""
    person: Person
    line_type: str  # paternal, maternal, paternal-maternal, etc.
    generation: int  # поколение от исходной персоны
    descendants_count: int  # сколько потомков в дереве
    data_quality: str  # good, partial, minimal
    research_priority: int  # 1-5, где 1 — высший приоритет


@dataclass
class LineAnalysis:
    """Анализ одной линии предков."""
    line_name: str
    depth: int  # количество поколений
    brick_wall: Optional[Person]
    earliest_year: Optional[int]
    persons_in_line: List[Person]


def get_person_year(person: Person) -> Optional[int]:
    """Получить год (рождения или смерти) для сортировки."""
    if person.birth_year:
        return person.birth_year
    if person.birth_date:
        return person.birth_date.year
    if person.death_year:
        return person.death_year
    if person.death_date:
        return person.death_date.year
    return None


def assess_data_quality(person: Person) -> str:
    """Оценка качества данных о персоне."""
    score = 0
    if person.birth_date:
        score += 3
    elif person.birth_year:
        score += 2
    if person.death_date:
        score += 2
    elif person.death_year:
        score += 1
    if person.birth_place:
        score += 2
    if person.surname:
        score += 1
    if person.given_name:
        score += 1
    if person.occupation:
        score += 1

    if score >= 8:
        return "good"
    elif score >= 4:
        return "partial"
    else:
        return "minimal"


def count_descendants(person: Person, data: GedcomData, visited: Set[str] = None) -> int:
    """Подсчёт всех потомков персоны."""
    if visited is None:
        visited = set()

    if person.id in visited:
        return 0

    visited.add(person.id)
    count = 0

    children = data.get_children(person)
    for child in children:
        count += 1
        count += count_descendants(child, data, visited)

    return count


def find_ancestors(person: Person, data: GedcomData, generation: int = 0,
                   line_path: str = "", visited: Set[str] = None) -> List[Tuple[Person, int, str]]:
    """
    Рекурсивный поиск всех предков.
    Возвращает список (персона, поколение, путь линии).
    """
    if visited is None:
        visited = set()

    if person.id in visited:
        return []

    visited.add(person.id)
    ancestors = []

    father, mother = data.get_parents(person)

    if father:
        new_path = line_path + "F" if line_path else "F"
        ancestors.append((father, generation + 1, new_path))
        ancestors.extend(find_ancestors(father, data, generation + 1, new_path, visited))

    if mother:
        new_path = line_path + "M" if line_path else "M"
        ancestors.append((mother, generation + 1, new_path))
        ancestors.extend(find_ancestors(mother, data, generation + 1, new_path, visited))

    return ancestors


def find_brick_walls(data: GedcomData, start_person: Optional[Person] = None) -> Tuple[List[BrickWall], Dict]:
    """
    Поиск всех кирпичных стен в дереве.
    """
    brick_walls = []
    stats = {
        'total_persons': len(data.persons),
        'with_parents': 0,
        'without_parents': 0,
        'end_of_lines': 0,
    }

    # Находим всех персон без родителей
    persons_without_parents = []
    for person_id, person in data.persons.items():
        father, mother = data.get_parents(person)
        if father or mother:
            stats['with_parents'] += 1
        else:
            stats['without_parents'] += 1
            persons_without_parents.append(person)

    # Если указана стартовая персона, находим предков только от неё
    if start_person:
        ancestors = find_ancestors(start_person, data)
        ancestor_ids = {a[0].id for a in ancestors}

        # Фильтруем только тех, кто является предком стартовой персоны
        relevant_walls = []
        for person in persons_without_parents:
            if person.id in ancestor_ids:
                # Находим информацию о линии
                for ancestor, gen, path in ancestors:
                    if ancestor.id == person.id:
                        relevant_walls.append((person, gen, path))
                        break

        # Создаём BrickWall объекты
        for person, generation, path in relevant_walls:
            line_type = path_to_line_name(path)
            descendants = count_descendants(person, data)
            quality = assess_data_quality(person)

            # Приоритет: чем ближе предок и чем больше потомков, тем выше
            priority = calculate_priority(generation, descendants, quality)

            brick_walls.append(BrickWall(
                person=person,
                line_type=line_type,
                generation=generation,
                descendants_count=descendants,
                data_quality=quality,
                research_priority=priority
            ))
    else:
        # Без стартовой персоны — анализируем всех без родителей
        for person in persons_without_parents:
            descendants = count_descendants(person, data)
            quality = assess_data_quality(person)
            priority = calculate_priority(0, descendants, quality)

            brick_walls.append(BrickWall(
                person=person,
                line_type="unknown",
                generation=0,
                descendants_count=descendants,
                data_quality=quality,
                research_priority=priority
            ))

    stats['end_of_lines'] = len(brick_walls)

    return brick_walls, stats


def path_to_line_name(path: str) -> str:
    """Преобразование пути (FFMF) в название линии."""
    if not path:
        return "корневая"

    names = {
        "F": "отцовская",
        "M": "материнская",
        "FF": "дед по отцу",
        "FM": "бабка по отцу",
        "MF": "дед по матери",
        "MM": "бабка по матери",
    }

    if path in names:
        return names[path]

    # Для длинных путей
    parts = []
    if path.startswith("F"):
        parts.append("отцовская")
    else:
        parts.append("материнская")

    depth = len(path) - 1
    if depth > 0:
        parts.append(f"({depth} пок. назад)")

    return " ".join(parts)


def calculate_priority(generation: int, descendants: int, quality: str) -> int:
    """
    Расчёт приоритета исследования.
    1 — высший приоритет, 5 — низший.
    """
    score = 0

    # Чем ближе предок, тем выше приоритет
    if generation <= 3:
        score += 3
    elif generation <= 5:
        score += 2
    else:
        score += 1

    # Чем больше потомков, тем выше приоритет
    if descendants >= 10:
        score += 3
    elif descendants >= 5:
        score += 2
    elif descendants >= 1:
        score += 1

    # Чем меньше данных, тем выше приоритет (больше можно найти)
    if quality == "minimal":
        score += 2
    elif quality == "partial":
        score += 1

    # Преобразуем в приоритет 1-5
    if score >= 7:
        return 1
    elif score >= 5:
        return 2
    elif score >= 3:
        return 3
    elif score >= 2:
        return 4
    else:
        return 5


def analyze_lines(data: GedcomData, start_person: Person) -> List[LineAnalysis]:
    """Анализ глубины каждой линии предков."""
    lines = []

    def trace_line(person: Person, get_parent_func, line_name: str) -> LineAnalysis:
        """Трассировка одной линии до конца."""
        persons_in_line = [person]
        current = person
        depth = 0

        while True:
            father, mother = data.get_parents(current)
            parent = get_parent_func(father, mother)
            if not parent:
                break
            persons_in_line.append(parent)
            current = parent
            depth += 1

        brick_wall = persons_in_line[-1] if len(persons_in_line) > 1 else None
        earliest_year = get_person_year(persons_in_line[-1]) if persons_in_line else None

        return LineAnalysis(
            line_name=line_name,
            depth=depth,
            brick_wall=brick_wall,
            earliest_year=earliest_year,
            persons_in_line=persons_in_line
        )

    # Прямая мужская линия (отец отца отца...)
    lines.append(trace_line(start_person, lambda f, m: f, "Прямая мужская (Y-хромосома)"))

    # Прямая женская линия (мать матери матери...)
    lines.append(trace_line(start_person, lambda f, m: m, "Прямая женская (митохондриальная)"))

    # Линия деда по отцу
    father, _ = data.get_parents(start_person)
    if father:
        grandfather, _ = data.get_parents(father)
        if grandfather:
            lines.append(trace_line(grandfather, lambda f, m: f, "Линия прадеда по отцу"))

    # Линия бабки по отцу
    if father:
        _, grandmother = data.get_parents(father)
        if grandmother:
            lines.append(trace_line(grandmother, lambda f, m: m, "Линия прабабки по отцу"))

    return lines


def main():
    parser = argparse.ArgumentParser(
        description='Анализ «кирпичных стен» (тупиков) в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--from', dest='start_id', metavar='ID',
                        help='ID персоны для анализа предков (например, @I1@)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    start_person = None
    if args.start_id:
        start_person = data.get_person(args.start_id)
        if not start_person:
            print(f"Ошибка: персона {args.start_id} не найдена")
            sys.exit(1)

    brick_walls, stats = find_brick_walls(data, start_person)

    # Формируем отчёт
    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ «КИРПИЧНЫХ СТЕН» — КОНЕЧНЫХ ПРЕДКОВ БЕЗ ИЗВЕСТНЫХ РОДИТЕЛЕЙ")
    if start_person:
        output_lines.append(f"(анализ предков: {start_person.name})")
    output_lines.append("=" * 100)

    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"  ├─ Всего персон в дереве: {stats['total_persons']}")
    output_lines.append(f"  ├─ С известными родителями: {stats['with_parents']}")
    output_lines.append(f"  ├─ Без известных родителей: {stats['without_parents']}")
    output_lines.append(f"  └─ Конечных предков (brick walls): {stats['end_of_lines']}")

    # Анализ линий если есть стартовая персона
    if start_person:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📈 АНАЛИЗ ГЛУБИНЫ ЛИНИЙ")
        output_lines.append("=" * 100)

        lines = analyze_lines(data, start_person)
        for line in lines:
            output_lines.append(f"\n🔹 {line.line_name}")
            output_lines.append(f"   Глубина: {line.depth} поколений")
            if line.earliest_year:
                output_lines.append(f"   Самый ранний год: {line.earliest_year}")
            if line.brick_wall:
                output_lines.append(f"   Конечный предок: {line.brick_wall.name}")

    # Кирпичные стены по приоритету
    if brick_walls:
        # Сортируем по приоритету
        sorted_walls = sorted(brick_walls, key=lambda x: (x.research_priority, -x.descendants_count))

        output_lines.append("\n" + "=" * 100)
        output_lines.append("🧱 КИРПИЧНЫЕ СТЕНЫ ПО ПРИОРИТЕТУ ИССЛЕДОВАНИЯ")
        output_lines.append("=" * 100)

        priority_labels = {
            1: "🔴 ВЫСШИЙ",
            2: "🟠 ВЫСОКИЙ",
            3: "🟡 СРЕДНИЙ",
            4: "🟢 НИЗКИЙ",
            5: "⚪ МИНИМАЛЬНЫЙ"
        }

        for priority in range(1, 6):
            priority_walls = [w for w in sorted_walls if w.research_priority == priority]
            if priority_walls:
                output_lines.append(f"\n{priority_labels[priority]} ПРИОРИТЕТ ({len(priority_walls)}):")

                for wall in priority_walls[:15]:  # Ограничиваем вывод
                    person = wall.person
                    year = get_person_year(person)
                    year_str = f" ({year})" if year else ""

                    output_lines.append(f"\n   • {person.name}{year_str}")
                    if start_person and wall.line_type != "unknown":
                        output_lines.append(f"     Линия: {wall.line_type}")
                        output_lines.append(f"     Поколение: {wall.generation}")
                    output_lines.append(f"     Потомков в дереве: {wall.descendants_count}")
                    output_lines.append(f"     Качество данных: {wall.data_quality}")

                    # Подсказки для исследования
                    hints = []
                    if person.birth_place:
                        hints.append(f"Место рождения: {person.birth_place}")
                    if person.occupation:
                        hints.append(f"Занятие: {person.occupation}")
                    if person.surname:
                        hints.append(f"Фамилия: {person.surname}")

                    if hints:
                        output_lines.append(f"     Подсказки: {'; '.join(hints)}")

                if len(priority_walls) > 15:
                    output_lines.append(f"\n   ... и ещё {len(priority_walls) - 15}")

    # Статистика по фамилиям среди brick walls
    if brick_walls:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📊 ФАМИЛИИ СРЕДИ КОНЕЧНЫХ ПРЕДКОВ")
        output_lines.append("=" * 100)

        by_surname = defaultdict(list)
        for wall in brick_walls:
            surname = wall.person.surname or "(без фамилии)"
            by_surname[surname].append(wall)

        sorted_surnames = sorted(by_surname.items(), key=lambda x: -len(x[1]))
        for surname, walls in sorted_surnames[:20]:
            output_lines.append(f"  {surname}: {len(walls)} персон")

    # Рекомендации
    output_lines.append("\n" + "=" * 100)
    output_lines.append("💡 РЕКОМЕНДАЦИИ ДЛЯ ИССЛЕДОВАНИЯ")
    output_lines.append("=" * 100)

    output_lines.append("""
  1. Начните с предков ВЫСШЕГО приоритета — они ближе и дадут больше информации
  2. Используйте место рождения/жительства для поиска в метрических книгах
  3. Обратите внимание на фамилии — однофамильцы могут быть родственниками
  4. Для предков с датами — ищите записи о крещении (±8 дней от рождения)
  5. Занятие (profession) может указать на сословие и тип архивных документов
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
