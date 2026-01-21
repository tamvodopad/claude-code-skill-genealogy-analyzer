#!/usr/bin/env python3
"""
Экспорт генеалогических данных для визуализации.
Форматы: JSON, CSV, HTML timeline.

Использование:
    python3 timeline_export.py tree.ged --format json -o events.json
    python3 timeline_export.py tree.ged --format csv -o events.csv
    python3 timeline_export.py tree.ged --format html -o timeline.html
"""

import sys
import argparse
import json
import csv
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from datetime import date

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class TimelineEvent:
    """Событие для таймлайна."""
    date: str
    year: int
    month: Optional[int]
    day: Optional[int]
    event_type: str
    title: str
    description: str
    person_id: str
    person_name: str
    place: Optional[str]
    family_id: Optional[str]


def get_date_parts(date_obj) -> tuple:
    """Получить компоненты даты."""
    year = None
    month = None
    day = None

    if date_obj:
        if hasattr(date_obj, 'year'):
            year = date_obj.year
        if hasattr(date_obj, 'month'):
            month = date_obj.month
        if hasattr(date_obj, 'day'):
            day = date_obj.day

    return year, month, day


def format_date(year: int, month: Optional[int] = None, day: Optional[int] = None) -> str:
    """Форматировать дату."""
    if year:
        if month and day:
            return f"{year:04d}-{month:02d}-{day:02d}"
        elif month:
            return f"{year:04d}-{month:02d}"
        else:
            return f"{year:04d}"
    return ""


def extract_events(data: GedcomData, include_types: List[str] = None) -> List[TimelineEvent]:
    """Извлечь события из данных."""
    events = []

    default_types = ['birth', 'death', 'marriage']
    types_to_include = include_types or default_types

    # События персон
    for person_id, person in data.persons.items():
        # Рождение
        if 'birth' in types_to_include:
            year, month, day = get_date_parts(person.birth_date)
            if not year:
                year = person.birth_year

            if year:
                event = TimelineEvent(
                    date=format_date(year, month, day),
                    year=year,
                    month=month,
                    day=day,
                    event_type='birth',
                    title=f"Рождение: {person.name}",
                    description=f"Родился(ась) {person.name}",
                    person_id=person.id,
                    person_name=person.name,
                    place=person.birth_place,
                    family_id=person.child_family_id
                )
                events.append(event)

        # Смерть
        if 'death' in types_to_include:
            year, month, day = get_date_parts(person.death_date)
            if not year:
                year = person.death_year

            if year:
                age = None
                birth_year = person.birth_date.year if person.birth_date else person.birth_year
                if birth_year:
                    age = year - birth_year

                age_str = f" ({age} лет)" if age else ""
                event = TimelineEvent(
                    date=format_date(year, month, day),
                    year=year,
                    month=month,
                    day=day,
                    event_type='death',
                    title=f"Смерть: {person.name}",
                    description=f"Умер(ла) {person.name}{age_str}",
                    person_id=person.id,
                    person_name=person.name,
                    place=getattr(person, 'death_place', None),
                    family_id=None
                )
                events.append(event)

    # Браки
    if 'marriage' in types_to_include:
        for family_id, family in data.families.items():
            year, month, day = get_date_parts(family.marriage_date)
            if not year:
                year = family.marriage_year

            if year:
                husband = data.get_person(family.husband_id) if family.husband_id else None
                wife = data.get_person(family.wife_id) if family.wife_id else None

                h_name = husband.name if husband else "?"
                w_name = wife.name if wife else "?"

                event = TimelineEvent(
                    date=format_date(year, month, day),
                    year=year,
                    month=month,
                    day=day,
                    event_type='marriage',
                    title=f"Брак: {h_name} + {w_name}",
                    description=f"Бракосочетание {h_name} и {w_name}",
                    person_id=family.husband_id or family.wife_id or "",
                    person_name=f"{h_name} + {w_name}",
                    place=family.marriage_place,
                    family_id=family.id
                )
                events.append(event)

    # Сортируем по дате
    events.sort(key=lambda e: (e.year, e.month or 0, e.day or 0))

    return events


def export_json(events: List[TimelineEvent], output_file: str):
    """Экспорт в JSON."""
    data = [asdict(e) for e in events]

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_csv(events: List[TimelineEvent], output_file: str):
    """Экспорт в CSV."""
    fieldnames = ['date', 'year', 'month', 'day', 'event_type', 'title',
                  'description', 'person_id', 'person_name', 'place', 'family_id']

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow(asdict(event))


def export_html(events: List[TimelineEvent], output_file: str):
    """Экспорт в HTML timeline."""
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Генеалогический таймлайн</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }
        h1 {
            text-align: center;
            color: #333;
        }
        .timeline {
            max-width: 800px;
            margin: 0 auto;
            position: relative;
            padding: 20px 0;
        }
        .timeline::before {
            content: '';
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            width: 4px;
            height: 100%;
            background: #ddd;
        }
        .event {
            position: relative;
            margin: 20px 0;
            padding: 15px 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            width: 45%;
        }
        .event:nth-child(odd) {
            margin-left: 5%;
        }
        .event:nth-child(even) {
            margin-left: 50%;
        }
        .event::before {
            content: '';
            position: absolute;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            top: 20px;
        }
        .event:nth-child(odd)::before {
            right: -28px;
        }
        .event:nth-child(even)::before {
            left: -28px;
        }
        .event.birth::before { background: #4CAF50; }
        .event.death::before { background: #f44336; }
        .event.marriage::before { background: #FF9800; }
        .date {
            font-size: 0.85em;
            color: #666;
            margin-bottom: 5px;
        }
        .title {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        .description {
            font-size: 0.9em;
            color: #555;
        }
        .place {
            font-size: 0.8em;
            color: #888;
            margin-top: 5px;
        }
        .stats {
            text-align: center;
            margin: 20px 0;
            color: #666;
        }
        .legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .legend-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .legend-dot.birth { background: #4CAF50; }
        .legend-dot.death { background: #f44336; }
        .legend-dot.marriage { background: #FF9800; }
        @media (max-width: 600px) {
            .event {
                width: 85%;
                margin-left: 10% !important;
            }
            .event::before {
                left: -20px !important;
                right: auto !important;
            }
            .timeline::before {
                left: 20px;
            }
        }
    </style>
</head>
<body>
    <h1>🌳 Генеалогический таймлайн</h1>

    <div class="legend">
        <div class="legend-item">
            <div class="legend-dot birth"></div>
            <span>Рождение</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot marriage"></div>
            <span>Брак</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot death"></div>
            <span>Смерть</span>
        </div>
    </div>

    <div class="stats">
        Всего событий: {total_events} | Период: {min_year} - {max_year}
    </div>

    <div class="timeline">
{events_html}
    </div>

    <script>
        // Можно добавить интерактивность
    </script>
</body>
</html>
"""

    events_html_parts = []
    for event in events:
        place_html = f'<div class="place">📍 {event.place}</div>' if event.place else ''
        event_html = f'''        <div class="event {event.event_type}">
            <div class="date">{event.date}</div>
            <div class="title">{event.title}</div>
            <div class="description">{event.description}</div>
            {place_html}
        </div>'''
        events_html_parts.append(event_html)

    events_html = '\n'.join(events_html_parts)

    years = [e.year for e in events if e.year]
    min_year = min(years) if years else 0
    max_year = max(years) if years else 0

    html = html.format(
        total_events=len(events),
        min_year=min_year,
        max_year=max_year,
        events_html=events_html
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(
        description='Экспорт генеалогических данных для визуализации'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--format', '-f', choices=['json', 'csv', 'html'],
                        default='json', help='Формат экспорта')
    parser.add_argument('--output', '-o', required=True, metavar='FILE',
                        help='Выходной файл')
    parser.add_argument('--types', nargs='+',
                        choices=['birth', 'death', 'marriage'],
                        help='Типы событий для экспорта')
    parser.add_argument('--from-year', type=int, metavar='YEAR',
                        help='Начальный год')
    parser.add_argument('--to-year', type=int, metavar='YEAR',
                        help='Конечный год')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей")

    # Извлекаем события
    events = extract_events(data, args.types)

    # Фильтруем по годам
    if args.from_year:
        events = [e for e in events if e.year >= args.from_year]
    if args.to_year:
        events = [e for e in events if e.year <= args.to_year]

    print(f"Извлечено событий: {len(events)}")

    # Экспорт
    if args.format == 'json':
        export_json(events, args.output)
    elif args.format == 'csv':
        export_csv(events, args.output)
    elif args.format == 'html':
        export_html(events, args.output)

    print(f"\n✅ Экспортировано в: {args.output}")

    # Краткая статистика
    births = sum(1 for e in events if e.event_type == 'birth')
    deaths = sum(1 for e in events if e.event_type == 'death')
    marriages = sum(1 for e in events if e.event_type == 'marriage')

    print(f"\n📊 Статистика:")
    print(f"   Рождений: {births}")
    print(f"   Смертей: {deaths}")
    print(f"   Браков: {marriages}")

    if events:
        years = [e.year for e in events]
        print(f"   Период: {min(years)}-{max(years)}")


if __name__ == '__main__':
    main()
