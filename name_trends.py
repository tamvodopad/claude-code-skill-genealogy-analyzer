#!/usr/bin/env python3
"""
Анализ трендов имён в генеалогическом древе.
Популярность имён по периодам, редкие имена, изменения.

Использование:
    python3 name_trends.py tree.ged
    python3 name_trends.py tree.ged --name Иван
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def get_given_name(person: Person) -> Optional[str]:
    """Получить имя."""
    if hasattr(person, 'given_name') and person.given_name:
        return person.given_name.strip()

    if person.name:
        # Убираем фамилию в слэшах и берём первое слово
        name = person.name.replace('/', ' ').strip()
        parts = name.split()
        if parts:
            return parts[0].strip()

    return None


def normalize_name(name: str) -> str:
    """Нормализовать имя."""
    if not name:
        return ""

    # Базовая нормализация
    n = name.strip().lower()

    # Варианты одного имени
    name_variants = {
        'александр': ['саша', 'шура', 'алекс'],
        'екатерина': ['катя', 'катерина'],
        'мария': ['маша', 'марья', 'маруся'],
        'анна': ['аня', 'анюта', 'нюра'],
        'иван': ['ваня', 'иоанн'],
        'михаил': ['миша', 'михайло'],
        'николай': ['коля', 'никола'],
        'пётр': ['петя', 'петро', 'петр'],
        'василий': ['вася', 'василь'],
        'дмитрий': ['дима', 'димитрий', 'митя'],
        'алексей': ['алёша', 'лёша', 'алексий'],
        'сергей': ['серёжа', 'сергий'],
        'андрей': ['андрюша'],
        'владимир': ['вова', 'володя'],
        'григорий': ['гриша', 'григор'],
        'фёдор': ['федя', 'федор', 'феодор'],
        'степан': ['стёпа', 'степа'],
        'тимофей': ['тима'],
        'евдокия': ['дуня', 'авдотья'],
        'прасковья': ['параша', 'параскева'],
        'пелагея': ['поля', 'палагея'],
        'ксения': ['ксюша', 'аксинья'],
        'наталья': ['наташа', 'наталия'],
        'елизавета': ['лиза'],
        'татьяна': ['таня'],
        'ольга': ['оля'],
    }

    # Проверяем варианты
    for canonical, variants in name_variants.items():
        if n == canonical or n in variants:
            return canonical
        # Проверяем без ё/е
        n_ye = n.replace('ё', 'е')
        canonical_ye = canonical.replace('ё', 'е')
        if n_ye == canonical_ye:
            return canonical

    return n


def analyze_name_trends(data: GedcomData) -> Dict:
    """Анализ трендов имён."""
    stats = {
        'total_persons': 0,
        'with_names': 0,
        'male_names': defaultdict(lambda: {'total': 0, 'by_decade': defaultdict(int)}),
        'female_names': defaultdict(lambda: {'total': 0, 'by_decade': defaultdict(int)}),
        'by_decade': defaultdict(lambda: {'M': defaultdict(int), 'F': defaultdict(int)}),
        'rare_names': [],
        'name_longevity': {},  # когда имя появилось и исчезло
    }

    for person_id, person in data.persons.items():
        stats['total_persons'] += 1

        given_name = get_given_name(person)
        if not given_name:
            continue

        stats['with_names'] += 1

        normalized = normalize_name(given_name)
        birth_year = get_birth_year(person)
        decade = (birth_year // 10) * 10 if birth_year else None
        sex = person.sex

        if sex == 'M':
            stats['male_names'][normalized]['total'] += 1
            if decade:
                stats['male_names'][normalized]['by_decade'][decade] += 1
                stats['by_decade'][decade]['M'][normalized] += 1
        elif sex == 'F':
            stats['female_names'][normalized]['total'] += 1
            if decade:
                stats['female_names'][normalized]['by_decade'][decade] += 1
                stats['by_decade'][decade]['F'][normalized] += 1

        # Отслеживаем период использования имени
        if normalized not in stats['name_longevity']:
            stats['name_longevity'][normalized] = {'first': birth_year, 'last': birth_year, 'sex': sex}
        else:
            if birth_year:
                if stats['name_longevity'][normalized]['first'] is None or birth_year < stats['name_longevity'][normalized]['first']:
                    stats['name_longevity'][normalized]['first'] = birth_year
                if stats['name_longevity'][normalized]['last'] is None or birth_year > stats['name_longevity'][normalized]['last']:
                    stats['name_longevity'][normalized]['last'] = birth_year

    # Находим редкие имена (1-2 носителя)
    for name, data_m in stats['male_names'].items():
        if data_m['total'] <= 2:
            stats['rare_names'].append((name, 'M', data_m['total']))

    for name, data_f in stats['female_names'].items():
        if data_f['total'] <= 2:
            stats['rare_names'].append((name, 'F', data_f['total']))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ трендов имён'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--name', metavar='NAME',
                        help='Детальный анализ конкретного имени')
    parser.add_argument('--top', type=int, default=20,
                        help='Количество имён в топе (по умолчанию 20)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ТРЕНДОВ ИМЁН")
    output_lines.append("=" * 100)

    stats = analyze_name_trends(data)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего персон: {stats['total_persons']}")
    output_lines.append(f"   С известными именами: {stats['with_names']}")
    output_lines.append(f"   Уникальных мужских имён: {len(stats['male_names'])}")
    output_lines.append(f"   Уникальных женских имён: {len(stats['female_names'])}")

    # Анализ конкретного имени
    if args.name:
        normalized = normalize_name(args.name)
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"🔍 АНАЛИЗ ИМЕНИ: {args.name.upper()}")
        output_lines.append("=" * 100)

        found_m = stats['male_names'].get(normalized)
        found_f = stats['female_names'].get(normalized)

        if found_m:
            output_lines.append(f"\n   Мужское имя: {found_m['total']} носителей")
            if found_m['by_decade']:
                output_lines.append("   По десятилетиям:")
                for decade in sorted(found_m['by_decade'].keys()):
                    count = found_m['by_decade'][decade]
                    output_lines.append(f"      {decade}s: {count}")

        if found_f:
            output_lines.append(f"\n   Женское имя: {found_f['total']} носителей")
            if found_f['by_decade']:
                output_lines.append("   По десятилетиям:")
                for decade in sorted(found_f['by_decade'].keys()):
                    count = found_f['by_decade'][decade]
                    output_lines.append(f"      {decade}s: {count}")

        if not found_m and not found_f:
            output_lines.append(f"\n   Имя '{args.name}' не найдено в древе")

        # Период использования
        if normalized in stats['name_longevity']:
            longevity = stats['name_longevity'][normalized]
            if longevity['first'] and longevity['last']:
                span = longevity['last'] - longevity['first']
                output_lines.append(f"\n   Период использования: {longevity['first']}-{longevity['last']} ({span} лет)")

    # Топ мужских имён
    output_lines.append("\n" + "=" * 100)
    output_lines.append("👨 ТОП МУЖСКИХ ИМЁН")
    output_lines.append("=" * 100)

    sorted_male = sorted(stats['male_names'].items(), key=lambda x: -x[1]['total'])
    total_male = sum(d['total'] for d in stats['male_names'].values())

    for i, (name, data_n) in enumerate(sorted_male[:args.top], 1):
        pct = data_n['total'] / total_male * 100 if total_male > 0 else 0
        output_lines.append(f"   {i:>2}. {name.capitalize():<15} {data_n['total']:>5} ({pct:.1f}%)")

    # Топ женских имён
    output_lines.append("\n" + "=" * 100)
    output_lines.append("👩 ТОП ЖЕНСКИХ ИМЁН")
    output_lines.append("=" * 100)

    sorted_female = sorted(stats['female_names'].items(), key=lambda x: -x[1]['total'])
    total_female = sum(d['total'] for d in stats['female_names'].values())

    for i, (name, data_n) in enumerate(sorted_female[:args.top], 1):
        pct = data_n['total'] / total_female * 100 if total_female > 0 else 0
        output_lines.append(f"   {i:>2}. {name.capitalize():<15} {data_n['total']:>5} ({pct:.1f}%)")

    # Тренды по десятилетиям
    if stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 ПОПУЛЯРНЫЕ ИМЕНА ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        for decade in sorted(stats['by_decade'].keys()):
            decade_data = stats['by_decade'][decade]

            # Топ-3 мужских
            top_m = sorted(decade_data['M'].items(), key=lambda x: -x[1])[:3]
            # Топ-3 женских
            top_f = sorted(decade_data['F'].items(), key=lambda x: -x[1])[:3]

            if top_m or top_f:
                output_lines.append(f"\n   {decade}s:")
                if top_m:
                    m_str = ", ".join(f"{n.capitalize()}({c})" for n, c in top_m)
                    output_lines.append(f"      👨 {m_str}")
                if top_f:
                    f_str = ", ".join(f"{n.capitalize()}({c})" for n, c in top_f)
                    output_lines.append(f"      👩 {f_str}")

    # Редкие имена
    if stats['rare_names']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("💎 РЕДКИЕ ИМЕНА (1-2 носителя)")
        output_lines.append("=" * 100)

        rare_sorted = sorted(stats['rare_names'], key=lambda x: (x[1], x[0]))

        male_rare = [r for r in rare_sorted if r[1] == 'M']
        female_rare = [r for r in rare_sorted if r[1] == 'F']

        if male_rare:
            output_lines.append(f"\n   Мужские ({len(male_rare)}):")
            names_str = ", ".join(n.capitalize() for n, s, c in male_rare[:30])
            output_lines.append(f"      {names_str}")

        if female_rare:
            output_lines.append(f"\n   Женские ({len(female_rare)}):")
            names_str = ", ".join(n.capitalize() for n, s, c in female_rare[:30])
            output_lines.append(f"      {names_str}")

    # Имена-долгожители
    if stats['name_longevity']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("⏳ ИМЕНА С ДОЛГОЙ ИСТОРИЕЙ")
        output_lines.append("=" * 100)

        long_lived = []
        for name, longevity in stats['name_longevity'].items():
            if longevity['first'] and longevity['last']:
                span = longevity['last'] - longevity['first']
                count = stats['male_names'].get(name, {}).get('total', 0) + \
                       stats['female_names'].get(name, {}).get('total', 0)
                if span > 0 and count >= 3:
                    long_lived.append((name, longevity['first'], longevity['last'], span, count))

        long_lived.sort(key=lambda x: -x[3])

        for name, first, last, span, count in long_lived[:15]:
            output_lines.append(f"   {name.capitalize():<15} {first}-{last} ({span} лет, {count} носителей)")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Традиции именования в России:

   📿 До 1917 года:
   • Имена давались по святцам (православный календарь)
   • Популярные: Иван, Пётр, Василий, Мария, Анна, Екатерина
   • Имена повторялись в семьях (в честь родственников)
   • Региональные предпочтения

   ⭐ После 1917 года:
   • Революционные имена: Октябрина, Владлен, Сталина
   • Иностранные имена: Эдуард, Альберт
   • Упрощение старых имён

   📈 Тренды:
   • Некоторые имена стабильны веками (Иван, Мария)
   • Другие появляются и исчезают (мода)
   • Редкие имена могут указывать на происхождение

   🔍 Анализ редких имён:
   • Возможно ошибки транскрипции
   • Региональные варианты
   • Иностранное происхождение
   • Семейные традиции
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
