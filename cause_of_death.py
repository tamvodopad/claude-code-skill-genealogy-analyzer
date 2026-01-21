#!/usr/bin/env python3
"""
Анализ причин смерти в генеалогическом древе.
Категоризация, тренды по периодам, возрастные паттерны.

Использование:
    python3 cause_of_death.py tree.ged
    python3 cause_of_death.py tree.ged --period 1850-1920
    python3 cause_of_death.py tree.ged --cause "холера"
"""

import sys
import argparse
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


# Категории причин смерти
CAUSE_CATEGORIES = {
    'инфекционные': [
        'холера', 'тиф', 'оспа', 'чума', 'дизентерия', 'скарлатина',
        'корь', 'дифтерия', 'коклюш', 'туберкулёз', 'чахотка', 'горячка',
        'лихорадка', 'воспаление', 'грипп', 'испанка', 'малярия',
        'сыпной', 'брюшной', 'тифозная', 'инфлюэнца'
    ],
    'младенческие': [
        'от родов', 'при родах', 'родимец', 'младенческая', 'слабость',
        'недоношенность', 'от слабости', 'новорождённый', 'мертворождён',
        'от рождения', 'родовая', 'послеродовая'
    ],
    'несчастные_случаи': [
        'утонул', 'утопление', 'убит', 'убийство', 'пожар', 'сгорел',
        'замёрз', 'упал', 'падение', 'несчастный случай', 'травма',
        'отравление', 'угорел', 'молния', 'удар', 'задавлен'
    ],
    'военные': [
        'убит в бою', 'погиб на войне', 'ранение', 'пропал без вести',
        'военные действия', 'на фронте', 'в плену', 'расстрелян',
        'репрессирован', 'контузия'
    ],
    'сердечно-сосудистые': [
        'апоплексия', 'удар', 'паралич', 'сердце', 'сердечная',
        'инфаркт', 'инсульт', 'кровоизлияние'
    ],
    'онкология': [
        'рак', 'опухоль', 'новообразование', 'саркома', 'карцинома'
    ],
    'старость': [
        'старость', 'от старости', 'дряхлость', 'естественная смерть',
        'по старости', 'маразм', 'старческая'
    ],
    'голод': [
        'голод', 'истощение', 'от голода', 'голодная смерть',
        'дистрофия', 'недоедание'
    ],
    'неизвестно': [
        'неизвестно', 'не указана', 'внезапная', 'скоропостижная'
    ]
}


@dataclass
class DeathRecord:
    """Запись о смерти с причиной."""
    person: Person
    cause: str
    category: str
    year: Optional[int]
    age: Optional[int]
    place: Optional[str]


def get_death_year(person: Person) -> Optional[int]:
    """Получить год смерти."""
    if person.death_date:
        return person.death_date.year
    return person.death_year


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def get_death_cause(person: Person) -> Optional[str]:
    """Получить причину смерти из GEDCOM."""
    # Причина смерти может быть в разных местах
    if hasattr(person, 'death_cause') and person.death_cause:
        return person.death_cause.strip()

    # Проверяем notes на упоминание причины смерти
    if hasattr(person, 'notes') and person.notes:
        notes = person.notes if isinstance(person.notes, list) else [person.notes]
        for note in notes:
            if note:
                note_lower = note.lower()
                # Ищем паттерны типа "причина смерти:", "умер от"
                patterns = [
                    r'причина смерти[:\s]+([^.]+)',
                    r'умер(?:ла)? от\s+([^.]+)',
                    r'скончал(?:ся|ась) от\s+([^.]+)',
                    r'погиб(?:ла)?\s+([^.]+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, note_lower)
                    if match:
                        return match.group(1).strip()

    return None


def categorize_cause(cause: str) -> str:
    """Определить категорию причины смерти."""
    if not cause:
        return 'не указана'

    cause_lower = cause.lower()

    for category, keywords in CAUSE_CATEGORIES.items():
        for keyword in keywords:
            if keyword in cause_lower:
                return category

    return 'другое'


def analyze_death_causes(data: GedcomData, period: Tuple[int, int] = None) -> Dict:
    """Анализ причин смерти."""
    stats = {
        'total_deaths': 0,
        'with_cause': 0,
        'without_cause': 0,
        'records': [],
        'by_category': defaultdict(list),
        'by_decade': defaultdict(lambda: defaultdict(int)),
        'by_age_group': defaultdict(lambda: defaultdict(int)),
        'causes_list': defaultdict(int),
        'avg_age_by_category': {},
    }

    for person_id, person in data.persons.items():
        death_year = get_death_year(person)

        if not death_year:
            continue

        # Фильтр по периоду
        if period:
            if death_year < period[0] or death_year > period[1]:
                continue

        stats['total_deaths'] += 1

        cause = get_death_cause(person)
        category = categorize_cause(cause) if cause else 'не указана'

        birth_year = get_birth_year(person)
        age = death_year - birth_year if birth_year else None

        record = DeathRecord(
            person=person,
            cause=cause or '',
            category=category,
            year=death_year,
            age=age,
            place=getattr(person, 'death_place', None)
        )

        if cause:
            stats['with_cause'] += 1
            stats['causes_list'][cause.lower()] += 1
        else:
            stats['without_cause'] += 1

        stats['records'].append(record)
        stats['by_category'][category].append(record)

        # По десятилетиям
        decade = (death_year // 10) * 10
        stats['by_decade'][decade][category] += 1

        # По возрастным группам
        if age is not None:
            if age < 1:
                age_group = '0 (младенцы)'
            elif age < 5:
                age_group = '1-4'
            elif age < 15:
                age_group = '5-14'
            elif age < 30:
                age_group = '15-29'
            elif age < 50:
                age_group = '30-49'
            elif age < 70:
                age_group = '50-69'
            else:
                age_group = '70+'
            stats['by_age_group'][age_group][category] += 1

    # Средний возраст по категориям
    for category, records in stats['by_category'].items():
        ages = [r.age for r in records if r.age is not None]
        if ages:
            stats['avg_age_by_category'][category] = sum(ages) / len(ages)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ причин смерти'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--period', metavar='YYYY-YYYY',
                        help='Период анализа (например, 1850-1920)')
    parser.add_argument('--cause', metavar='TEXT',
                        help='Поиск конкретной причины смерти')
    parser.add_argument('--category', metavar='NAME',
                        help='Фильтр по категории')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    # Парсинг периода
    period = None
    if args.period:
        try:
            start, end = args.period.split('-')
            period = (int(start), int(end))
        except ValueError:
            print(f"Ошибка: неверный формат периода '{args.period}'. Используйте YYYY-YYYY")
            sys.exit(1)

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ПРИЧИН СМЕРТИ")
    output_lines.append("=" * 100)

    stats = analyze_death_causes(data, period)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    if period:
        output_lines.append(f"   Период: {period[0]}-{period[1]}")
    output_lines.append(f"   Всего смертей с датами: {stats['total_deaths']}")

    if stats['total_deaths'] > 0:
        with_pct = stats['with_cause'] / stats['total_deaths'] * 100
        output_lines.append(f"   С указанной причиной: {stats['with_cause']} ({with_pct:.1f}%)")
        output_lines.append(f"   Без указания причины: {stats['without_cause']}")

    # Поиск конкретной причины
    if args.cause:
        search_term = args.cause.lower()
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"🔍 ПОИСК: \"{args.cause}\"")
        output_lines.append("=" * 100)

        found = [r for r in stats['records']
                 if r.cause and search_term in r.cause.lower()]

        if found:
            output_lines.append(f"\n   Найдено: {len(found)} случаев")
            for r in found[:30]:
                age_str = f", {r.age} лет" if r.age else ""
                place_str = f", {r.place}" if r.place else ""
                output_lines.append(f"   • {r.person.name} ({r.year}{age_str}{place_str})")
                output_lines.append(f"     Причина: {r.cause}")
        else:
            output_lines.append(f"\n   Не найдено случаев с причиной \"{args.cause}\"")

    # По категориям
    if stats['by_category']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📋 ПО КАТЕГОРИЯМ")
        output_lines.append("=" * 100)

        # Сортируем по количеству
        sorted_cats = sorted(stats['by_category'].items(),
                            key=lambda x: -len(x[1]))

        for category, records in sorted_cats:
            if args.category and category != args.category:
                continue

            count = len(records)
            pct = count / stats['total_deaths'] * 100 if stats['total_deaths'] > 0 else 0
            avg_age = stats['avg_age_by_category'].get(category)
            avg_str = f", средний возраст: {avg_age:.1f}" if avg_age else ""

            output_lines.append(f"\n   {category.upper()}: {count} ({pct:.1f}%){avg_str}")

            # Примеры
            examples = records[:5]
            for r in examples:
                age_str = f", {r.age} лет" if r.age else ""
                cause_str = f" — {r.cause}" if r.cause else ""
                output_lines.append(f"      • {r.person.name} ({r.year}{age_str}){cause_str}")

            if len(records) > 5:
                output_lines.append(f"      ... и ещё {len(records) - 5}")

    # Уникальные причины смерти
    if stats['causes_list']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📝 УНИКАЛЬНЫЕ ПРИЧИНЫ СМЕРТИ")
        output_lines.append("=" * 100)

        sorted_causes = sorted(stats['causes_list'].items(), key=lambda x: -x[1])

        output_lines.append(f"\n   Топ причин:")
        for cause, count in sorted_causes[:25]:
            output_lines.append(f"   • {cause}: {count}")

    # По десятилетиям
    if stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        for decade in sorted(stats['by_decade'].keys()):
            decade_data = stats['by_decade'][decade]
            total = sum(decade_data.values())

            # Топ-3 причины
            top_causes = sorted(decade_data.items(), key=lambda x: -x[1])[:3]
            top_str = ", ".join(f"{c}({n})" for c, n in top_causes)

            output_lines.append(f"   {decade}s: {total} смертей — {top_str}")

    # По возрастным группам
    if stats['by_age_group']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👥 ПО ВОЗРАСТНЫМ ГРУППАМ")
        output_lines.append("=" * 100)

        age_order = ['0 (младенцы)', '1-4', '5-14', '15-29', '30-49', '50-69', '70+']

        for age_group in age_order:
            if age_group in stats['by_age_group']:
                group_data = stats['by_age_group'][age_group]
                total = sum(group_data.values())

                # Топ причины для возрастной группы
                top_causes = sorted(group_data.items(), key=lambda x: -x[1])[:3]
                top_str = ", ".join(f"{c}({n})" for c, n in top_causes)

                output_lines.append(f"   {age_group}: {total} — {top_str}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Причины смерти в метрических книгах России:

   📋 Терминология (до 1917):
   • «Горячка» — общее название лихорадочных болезней
   • «Чахотка» — туберкулёз лёгких
   • «Родимец» — судороги у младенцев
   • «Апоплексия» — инсульт
   • «Водянка» — отёки (часто сердечная недостаточность)
   • «Антонов огонь» — гангрена
   • «Грудная болезнь» — пневмония, бронхит

   ⚠️ Ограничения записей:
   • Диагнозы ставили священники, не врачи
   • Многие болезни не различались
   • Детские смерти часто без причины
   • «От старости» — любая смерть после 60-70

   📊 Типичная структура смертности (до 1917):
   • 30-50% — младенческая смертность (до 1 года)
   • 15-25% — инфекционные болезни
   • 10-15% — «старость» (естественные причины)
   • 5-10% — несчастные случаи, травмы

   🔍 На что обратить внимание:
   • Кластеры смертей от одной причины = эпидемия
   • Много «от голода» в определённый год = неурожай
   • Военные смерти молодых мужчин = война
   • Высокая младенческая смертность = норма для эпохи
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
