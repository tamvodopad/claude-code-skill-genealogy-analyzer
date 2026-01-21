#!/usr/bin/env python3
"""
Анализ продолжительности жизни в генеалогическом древе.
Статистика по поколениям, полу, местам, причинам смерти.

Использование:
    python3 longevity.py tree.ged
    python3 longevity.py tree.ged --by-century
    python3 longevity.py tree.ged --by-place
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
import statistics

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class LifespanData:
    """Данные о продолжительности жизни."""
    person: Person
    birth_year: int
    death_year: int
    age: int
    sex: str
    place: Optional[str]
    cause_of_death: Optional[str]


def calculate_age(person: Person) -> Optional[int]:
    """Вычисление возраста на момент смерти."""
    birth_year = None
    death_year = None

    if person.birth_date:
        birth_year = person.birth_date.year
    elif person.birth_year:
        birth_year = person.birth_year

    if person.death_date:
        death_year = person.death_date.year
    elif person.death_year:
        death_year = person.death_year

    if birth_year and death_year:
        age = death_year - birth_year
        if 0 <= age <= 120:  # Реалистичный возраст
            return age

    return None


def extract_cause_of_death(person: Person) -> Optional[str]:
    """Извлечение причины смерти (если указана)."""
    # В GEDCOM причина может быть в DEAT.CAUS или в NOTE
    if hasattr(person, 'death_cause') and person.death_cause:
        return person.death_cause
    return None


def collect_lifespan_data(data: GedcomData, before_year: Optional[int] = None,
                          after_year: Optional[int] = None,
                          exclude_infant: bool = False) -> List[LifespanData]:
    """Сбор данных о продолжительности жизни."""
    results = []

    for person_id, person in data.persons.items():
        age = calculate_age(person)
        if age is None:
            continue

        birth_year = person.birth_date.year if person.birth_date else person.birth_year
        death_year = person.death_date.year if person.death_date else person.death_year

        if not birth_year or not death_year:
            continue

        # Фильтры
        if before_year and birth_year > before_year:
            continue
        if after_year and birth_year < after_year:
            continue
        if exclude_infant and age < 5:
            continue

        results.append(LifespanData(
            person=person,
            birth_year=birth_year,
            death_year=death_year,
            age=age,
            sex=person.sex or 'U',
            place=person.birth_place,
            cause_of_death=extract_cause_of_death(person)
        ))

    return results


def analyze_by_period(lifespans: List[LifespanData], period: int = 50) -> Dict:
    """Анализ по периодам (полувекам или веком)."""
    by_period = defaultdict(list)

    for ls in lifespans:
        period_start = (ls.birth_year // period) * period
        by_period[period_start].append(ls)

    stats = {}
    for p, data in sorted(by_period.items()):
        ages = [ls.age for ls in data]
        ages_adult = [a for a in ages if a >= 5]

        stats[p] = {
            'count': len(data),
            'mean_all': statistics.mean(ages) if ages else 0,
            'mean_adult': statistics.mean(ages_adult) if ages_adult else 0,
            'median': statistics.median(ages) if ages else 0,
            'max': max(ages) if ages else 0,
            'infant_mortality': len([a for a in ages if a < 5]) / len(ages) * 100 if ages else 0,
            'ages': ages
        }

    return stats


def analyze_by_sex(lifespans: List[LifespanData]) -> Dict:
    """Анализ по полу."""
    by_sex = {'M': [], 'F': [], 'U': []}

    for ls in lifespans:
        by_sex[ls.sex].append(ls.age)

    stats = {}
    sex_names = {'M': 'Мужчины', 'F': 'Женщины', 'U': 'Не указан'}

    for sex, ages in by_sex.items():
        if not ages:
            continue
        ages_adult = [a for a in ages if a >= 5]

        stats[sex_names[sex]] = {
            'count': len(ages),
            'mean': statistics.mean(ages),
            'mean_adult': statistics.mean(ages_adult) if ages_adult else 0,
            'median': statistics.median(ages),
            'stdev': statistics.stdev(ages) if len(ages) > 1 else 0,
            'max': max(ages),
            'min': min(ages),
        }

    return stats


def analyze_by_place(lifespans: List[LifespanData], top_n: int = 15) -> Dict:
    """Анализ по местам."""
    by_place = defaultdict(list)

    for ls in lifespans:
        if ls.place:
            # Берём первую часть места
            place = ls.place.split(',')[0].strip()
            by_place[place].append(ls.age)

    stats = {}
    for place, ages in by_place.items():
        if len(ages) >= 3:  # Минимум 3 человека
            stats[place] = {
                'count': len(ages),
                'mean': statistics.mean(ages),
                'median': statistics.median(ages),
                'max': max(ages),
            }

    # Сортируем по количеству
    sorted_stats = dict(sorted(stats.items(), key=lambda x: -x[1]['count'])[:top_n])
    return sorted_stats


def find_long_lived(lifespans: List[LifespanData], min_age: int = 80) -> List[LifespanData]:
    """Поиск долгожителей."""
    return sorted([ls for ls in lifespans if ls.age >= min_age],
                  key=lambda x: -x.age)


def analyze_infant_mortality(data: GedcomData, before_year: Optional[int] = None) -> Dict:
    """Детальный анализ детской смертности."""
    stats = {
        'total_births': 0,
        'deaths_0': 0,      # до года
        'deaths_1_5': 0,    # 1-5 лет
        'deaths_5_15': 0,   # 5-15 лет
        'by_decade': defaultdict(lambda: {'births': 0, 'infant_deaths': 0}),
    }

    for person_id, person in data.persons.items():
        birth_year = person.birth_date.year if person.birth_date else person.birth_year
        if not birth_year:
            continue

        if before_year and birth_year > before_year:
            continue

        stats['total_births'] += 1
        decade = (birth_year // 10) * 10
        stats['by_decade'][decade]['births'] += 1

        age = calculate_age(person)
        if age is not None:
            if age < 1:
                stats['deaths_0'] += 1
                stats['by_decade'][decade]['infant_deaths'] += 1
            elif age < 5:
                stats['deaths_1_5'] += 1
                stats['by_decade'][decade]['infant_deaths'] += 1
            elif age < 15:
                stats['deaths_5_15'] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ продолжительности жизни в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Только рождённые до указанного года')
    parser.add_argument('--after', type=int, metavar='YEAR',
                        help='Только рождённые после указанного года')
    parser.add_argument('--by-century', action='store_true',
                        help='Группировка по векам')
    parser.add_argument('--by-place', action='store_true',
                        help='Статистика по местам')
    parser.add_argument('--exclude-infant', action='store_true',
                        help='Исключить умерших до 5 лет')
    parser.add_argument('--long-lived', type=int, default=80, metavar='AGE',
                        help='Порог долгожителей (по умолчанию: 80)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ПРОДОЛЖИТЕЛЬНОСТИ ЖИЗНИ")
    if args.before:
        output_lines.append(f"(рождённые до {args.before} года)")
    if args.after:
        output_lines.append(f"(рождённые после {args.after} года)")
    if args.exclude_infant:
        output_lines.append("(без умерших до 5 лет)")
    output_lines.append("=" * 100)

    # Сбор данных
    lifespans = collect_lifespan_data(data, args.before, args.after, args.exclude_infant)

    if not lifespans:
        output_lines.append("\n⚠️ Недостаточно данных для анализа")
        print("\n".join(output_lines))
        return

    all_ages = [ls.age for ls in lifespans]

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Персон с датами рождения и смерти: {len(lifespans)}")
    output_lines.append(f"   Средний возраст: {statistics.mean(all_ages):.1f} лет")
    output_lines.append(f"   Медианный возраст: {statistics.median(all_ages):.1f} лет")
    output_lines.append(f"   Стандартное отклонение: {statistics.stdev(all_ages):.1f} лет")
    output_lines.append(f"   Максимальный возраст: {max(all_ages)} лет")

    # Взрослые (5+)
    adult_ages = [a for a in all_ages if a >= 5]
    if adult_ages:
        output_lines.append(f"\n   Для доживших до 5 лет:")
        output_lines.append(f"      Средний возраст: {statistics.mean(adult_ages):.1f} лет")
        output_lines.append(f"      Медианный возраст: {statistics.median(adult_ages):.1f} лет")

    # По полу
    sex_stats = analyze_by_sex(lifespans)
    if sex_stats:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👫 СТАТИСТИКА ПО ПОЛУ")
        output_lines.append("=" * 100)

        for sex_name, stats in sex_stats.items():
            output_lines.append(f"\n   {sex_name}:")
            output_lines.append(f"      Количество: {stats['count']}")
            output_lines.append(f"      Средний возраст (все): {stats['mean']:.1f} лет")
            output_lines.append(f"      Средний возраст (5+): {stats['mean_adult']:.1f} лет")
            output_lines.append(f"      Медиана: {stats['median']:.1f} лет")
            output_lines.append(f"      Максимум: {stats['max']} лет")

    # По периодам
    period = 100 if args.by_century else 50
    period_name = "ВЕКАМ" if args.by_century else "ПОЛУВЕКАМ"
    period_stats = analyze_by_period(lifespans, period)

    if period_stats:
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"📅 СТАТИСТИКА ПО {period_name}")
        output_lines.append("=" * 100)

        for p, stats in period_stats.items():
            if args.by_century:
                period_label = f"{p}-{p+99}"
            else:
                period_label = f"{p}-{p+49}"

            output_lines.append(f"\n   {period_label}:")
            output_lines.append(f"      Количество: {stats['count']}")
            output_lines.append(f"      Средний возраст (все): {stats['mean_all']:.1f} лет")
            output_lines.append(f"      Средний возраст (5+): {stats['mean_adult']:.1f} лет")
            output_lines.append(f"      Максимальный: {stats['max']} лет")
            output_lines.append(f"      Детская смертность (<5): {stats['infant_mortality']:.1f}%")

    # По местам
    if args.by_place:
        place_stats = analyze_by_place(lifespans)
        if place_stats:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("📍 СТАТИСТИКА ПО МЕСТАМ")
            output_lines.append("=" * 100)

            output_lines.append(f"\n{'Место':<40} {'Кол-во':<8} {'Средн.':<8} {'Макс.':<8}")
            output_lines.append("-" * 70)

            for place, stats in place_stats.items():
                place_short = place[:38] + '..' if len(place) > 40 else place
                output_lines.append(f"{place_short:<40} {stats['count']:<8} "
                                   f"{stats['mean']:.1f}    {stats['max']}")

    # Долгожители
    long_lived = find_long_lived(lifespans, args.long_lived)
    if long_lived:
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"🎂 ДОЛГОЖИТЕЛИ ({args.long_lived}+ лет)")
        output_lines.append("=" * 100)

        for ls in long_lived[:20]:
            place_str = f" ({ls.place.split(',')[0]})" if ls.place else ""
            output_lines.append(f"   {ls.age} лет — {ls.person.name} ({ls.birth_year}-{ls.death_year}){place_str}")

        if len(long_lived) > 20:
            output_lines.append(f"\n   ... и ещё {len(long_lived) - 20} долгожителей")

    # Детская смертность
    infant_stats = analyze_infant_mortality(data, args.before)
    if infant_stats['total_births'] > 0:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👶 ДЕТСКАЯ СМЕРТНОСТЬ")
        output_lines.append("=" * 100)

        total = infant_stats['total_births']
        deaths_u5 = infant_stats['deaths_0'] + infant_stats['deaths_1_5']
        output_lines.append(f"\n   Всего рождений: {total}")
        output_lines.append(f"   Умерли до года: {infant_stats['deaths_0']} ({infant_stats['deaths_0']/total*100:.1f}%)")
        output_lines.append(f"   Умерли 1-5 лет: {infant_stats['deaths_1_5']} ({infant_stats['deaths_1_5']/total*100:.1f}%)")
        output_lines.append(f"   Умерли 5-15 лет: {infant_stats['deaths_5_15']} ({infant_stats['deaths_5_15']/total*100:.1f}%)")
        output_lines.append(f"   Всего умерли до 5: {deaths_u5} ({deaths_u5/total*100:.1f}%)")

    # Гистограмма возрастов
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📊 РАСПРЕДЕЛЕНИЕ ВОЗРАСТОВ")
    output_lines.append("=" * 100)

    age_buckets = defaultdict(int)
    for age in all_ages:
        bucket = (age // 10) * 10
        age_buckets[bucket] += 1

    max_count = max(age_buckets.values()) if age_buckets else 1
    for bucket in sorted(age_buckets.keys()):
        count = age_buckets[bucket]
        bar_len = int(50 * count / max_count)
        bar = "█" * bar_len
        pct = count / len(all_ages) * 100
        output_lines.append(f"   {bucket:>3}-{bucket+9:<3}: {bar} {count} ({pct:.1f}%)")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Ожидаемая продолжительность жизни в России:

   • XVIII век: ~30 лет (с учётом детской смертности)
   • XIX век: ~35-40 лет
   • Начало XX века: ~40-45 лет
   • СССР 1950-е: ~65 лет
   • Современность: ~70+ лет

   Факторы, влияющие на продолжительность:
   • Детская смертность (главный фактор в прошлом)
   • Войны и эпидемии
   • Уровень медицины
   • Социальный статус и достаток
   • Местоположение (город/деревня)

   ⚠️ Данные в GEDCOM часто неполны — о долгожителях
   записи сохраняются лучше, чем о младенцах.
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
