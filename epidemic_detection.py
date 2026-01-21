#!/usr/bin/env python3
"""
Детекция эпидемий по кластерам смертей в генеалогическом древе.
Поиск аномальных всплесков смертности по периодам и местам.

Использование:
    python3 epidemic_detection.py tree.ged
    python3 epidemic_detection.py tree.ged --threshold 3
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
import statistics

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


# Известные эпидемии в России
KNOWN_EPIDEMICS = {
    (1830, 1831): 'Холера',
    (1847, 1849): 'Холера',
    (1853, 1854): 'Холера',
    (1866, 1867): 'Холера',
    (1892, 1893): 'Холера',
    (1918, 1920): 'Испанка (грипп)',
    (1921, 1922): 'Голод и тиф',
    (1932, 1933): 'Голодомор',
    (1946, 1947): 'Голод',
}


@dataclass
class DeathCluster:
    """Кластер смертей."""
    year: int
    month: Optional[int]
    place: Optional[str]
    deaths: List[Person]
    death_count: int
    baseline: float  # среднее за предыдущие годы
    excess: float    # превышение над нормой
    possible_cause: Optional[str]
    age_distribution: Dict[str, int]  # детские, взрослые, пожилые


def get_death_year(person: Person) -> Optional[int]:
    """Получить год смерти."""
    if person.death_date:
        return person.death_date.year
    return person.death_year


def get_death_month(person: Person) -> Optional[int]:
    """Получить месяц смерти."""
    if person.death_date:
        return person.death_date.month
    return None


def get_death_place(person: Person) -> Optional[str]:
    """Получить место смерти."""
    if hasattr(person, 'death_place') and person.death_place:
        return person.death_place.split(',')[0].strip().lower()
    return None


def get_age_at_death(person: Person) -> Optional[int]:
    """Получить возраст на момент смерти."""
    birth_year = None
    if person.birth_date:
        birth_year = person.birth_date.year
    elif person.birth_year:
        birth_year = person.birth_year

    death_year = get_death_year(person)

    if birth_year and death_year:
        return death_year - birth_year
    return None


def categorize_age(age: Optional[int]) -> str:
    """Категоризовать возраст."""
    if age is None:
        return 'неизвестно'
    if age <= 5:
        return 'младенцы (0-5)'
    if age <= 15:
        return 'дети (6-15)'
    if age <= 45:
        return 'взрослые (16-45)'
    if age <= 65:
        return 'зрелые (46-65)'
    return 'пожилые (65+)'


def detect_epidemic_cause(year: int) -> Optional[str]:
    """Определить возможную причину эпидемии по году."""
    for (start, end), cause in KNOWN_EPIDEMICS.items():
        if start <= year <= end:
            return cause
    return None


def analyze_death_clusters(data: GedcomData, threshold: float = 2.0) -> Dict:
    """Анализ кластеров смертей."""
    stats = {
        'total_deaths': 0,
        'deaths_by_year': defaultdict(list),
        'deaths_by_year_month': defaultdict(list),
        'deaths_by_year_place': defaultdict(list),
        'clusters': [],
        'monthly_clusters': [],
        'place_clusters': []
    }

    # Собираем все смерти
    for person_id, person in data.persons.items():
        death_year = get_death_year(person)
        if not death_year:
            continue

        stats['total_deaths'] += 1
        stats['deaths_by_year'][death_year].append(person)

        death_month = get_death_month(person)
        if death_month:
            stats['deaths_by_year_month'][(death_year, death_month)].append(person)

        death_place = get_death_place(person)
        if death_place:
            stats['deaths_by_year_place'][(death_year, death_place)].append(person)

    # Анализ годовых кластеров
    years = sorted(stats['deaths_by_year'].keys())
    if len(years) < 5:
        return stats

    for i, year in enumerate(years):
        deaths = stats['deaths_by_year'][year]
        death_count = len(deaths)

        # Считаем базовую линию (среднее за предыдущие 5 лет)
        prev_years = [y for y in years[max(0, i-5):i] if y != year]
        if not prev_years:
            continue

        prev_counts = [len(stats['deaths_by_year'][y]) for y in prev_years]
        baseline = statistics.mean(prev_counts)
        std = statistics.stdev(prev_counts) if len(prev_counts) > 1 else 1

        # Проверяем превышение
        if baseline > 0 and std > 0:
            z_score = (death_count - baseline) / std
            if z_score >= threshold:
                # Распределение по возрасту
                age_dist = defaultdict(int)
                for person in deaths:
                    age = get_age_at_death(person)
                    category = categorize_age(age)
                    age_dist[category] += 1

                cluster = DeathCluster(
                    year=year,
                    month=None,
                    place=None,
                    deaths=deaths,
                    death_count=death_count,
                    baseline=baseline,
                    excess=z_score,
                    possible_cause=detect_epidemic_cause(year),
                    age_distribution=dict(age_dist)
                )
                stats['clusters'].append(cluster)

    # Анализ месячных кластеров (внутри года)
    for year in years:
        monthly = defaultdict(list)
        for (y, m), persons in stats['deaths_by_year_month'].items():
            if y == year:
                monthly[m] = persons

        if len(monthly) < 3:
            continue

        month_counts = [len(monthly.get(m, [])) for m in range(1, 13)]
        avg = statistics.mean(month_counts)
        std = statistics.stdev(month_counts) if month_counts else 1

        for month, persons in monthly.items():
            if avg > 0 and std > 0:
                z = (len(persons) - avg) / std if std > 0 else 0
                if z >= threshold and len(persons) >= 3:
                    age_dist = defaultdict(int)
                    for person in persons:
                        age = get_age_at_death(person)
                        category = categorize_age(age)
                        age_dist[category] += 1

                    cluster = DeathCluster(
                        year=year,
                        month=month,
                        place=None,
                        deaths=persons,
                        death_count=len(persons),
                        baseline=avg,
                        excess=z,
                        possible_cause=detect_epidemic_cause(year),
                        age_distribution=dict(age_dist)
                    )
                    stats['monthly_clusters'].append(cluster)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Детекция эпидемий по кластерам смертей'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--threshold', type=float, default=2.0,
                        help='Порог Z-score для детекции кластера (по умолчанию 2.0)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("ДЕТЕКЦИЯ ЭПИДЕМИЙ ПО КЛАСТЕРАМ СМЕРТЕЙ")
    output_lines.append(f"(порог Z-score: {args.threshold})")
    output_lines.append("=" * 100)

    stats = analyze_death_clusters(data, args.threshold)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего смертей с датами: {stats['total_deaths']}")
    output_lines.append(f"   Найдено годовых кластеров: {len(stats['clusters'])}")
    output_lines.append(f"   Найдено месячных кластеров: {len(stats['monthly_clusters'])}")

    # Годовые кластеры
    if stats['clusters']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🦠 ГОДОВЫЕ КЛАСТЕРЫ СМЕРТЕЙ (возможные эпидемии)")
        output_lines.append("=" * 100)

        # Сортируем по превышению
        sorted_clusters = sorted(stats['clusters'], key=lambda x: -x.excess)

        for cluster in sorted_clusters:
            cause_str = f" — {cluster.possible_cause}" if cluster.possible_cause else ""
            output_lines.append(f"\n   📅 {cluster.year}{cause_str}")
            output_lines.append(f"      Смертей: {cluster.death_count} (обычно ~{cluster.baseline:.1f})")
            output_lines.append(f"      Превышение: {cluster.excess:.1f}σ ({cluster.death_count / cluster.baseline:.1f}x)")

            # Распределение по возрасту
            if cluster.age_distribution:
                output_lines.append(f"      Возрастное распределение:")
                for age_cat, count in sorted(cluster.age_distribution.items(),
                                            key=lambda x: -x[1]):
                    pct = count / cluster.death_count * 100
                    output_lines.append(f"         {age_cat}: {count} ({pct:.1f}%)")

            # Список умерших
            output_lines.append(f"      Умершие:")
            for person in cluster.deaths[:10]:
                age = get_age_at_death(person)
                age_str = f", {age} лет" if age else ""
                sex_icon = "👨" if person.sex == 'M' else "👩" if person.sex == 'F' else "👤"
                output_lines.append(f"         {sex_icon} {person.name}{age_str}")

            if len(cluster.deaths) > 10:
                output_lines.append(f"         ... и ещё {len(cluster.deaths) - 10} человек")

    # Месячные кластеры
    if stats['monthly_clusters']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📆 МЕСЯЧНЫЕ КЛАСТЕРЫ СМЕРТЕЙ")
        output_lines.append("=" * 100)

        months_ru = ['', 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                    'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']

        sorted_monthly = sorted(stats['monthly_clusters'],
                               key=lambda x: (-x.excess, x.year, x.month))

        for cluster in sorted_monthly[:15]:
            month_name = months_ru[cluster.month] if cluster.month else '?'
            cause_str = f" — {cluster.possible_cause}" if cluster.possible_cause else ""
            output_lines.append(f"\n   📅 {month_name} {cluster.year}{cause_str}")
            output_lines.append(f"      Смертей: {cluster.death_count} (обычно ~{cluster.baseline:.1f}/месяц)")
            output_lines.append(f"      Превышение: {cluster.excess:.1f}σ")

            # Список умерших
            for person in cluster.deaths[:5]:
                age = get_age_at_death(person)
                age_str = f", {age} лет" if age else ""
                output_lines.append(f"         • {person.name}{age_str}")

    # Хронология смертей
    if stats['deaths_by_year']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📈 ХРОНОЛОГИЯ СМЕРТЕЙ")
        output_lines.append("=" * 100)

        years = sorted(stats['deaths_by_year'].keys())
        max_deaths = max(len(d) for d in stats['deaths_by_year'].values())

        for year in years:
            count = len(stats['deaths_by_year'][year])
            bar_len = int(40 * count / max_deaths) if max_deaths > 0 else 0
            bar = "█" * bar_len

            # Маркер аномалии
            anomaly = " ⚠️" if any(c.year == year for c in stats['clusters']) else ""
            cause = ""
            known = detect_epidemic_cause(year)
            if known:
                cause = f" [{known}]"

            output_lines.append(f"   {year}: {bar} {count}{anomaly}{cause}")

    # Известные эпидемии (справка)
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📚 ИЗВЕСТНЫЕ ЭПИДЕМИИ В РОССИИ")
    output_lines.append("=" * 100)

    for (start, end), cause in sorted(KNOWN_EPIDEMICS.items()):
        output_lines.append(f"   {start}-{end}: {cause}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Признаки эпидемии в данных:

   • Резкий рост смертей (>2σ от нормы)
   • Концентрация в определённые месяцы
   • Высокая смертность определённых возрастных групп:
     - Холера — все возрасты, особенно слабые
     - Дифтерия — преимущественно дети
     - Тиф — молодые взрослые
     - Испанка — молодые взрослые (20-40 лет)
     - Голод — дети и пожилые

   Сезонность:
   • Лето — холера, дизентерия
   • Зима — грипп, пневмония, тиф
   • Голод — весна (до нового урожая)

   ⚠️ Ограничения:
   • Неполнота данных (не все смерти записаны)
   • Отсутствие причин смерти
   • Малая выборка может давать ложные кластеры
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
