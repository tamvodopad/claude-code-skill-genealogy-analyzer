#!/usr/bin/env python3
"""
Анализ влияния войн на демографию в генеалогическом древе.
Смерти в военные периоды, потери мужского населения, послевоенные изменения.

Использование:
    python3 war_impact.py tree.ged
    python3 war_impact.py tree.ged --war ww2
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
import statistics

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


# Основные войны России
WARS = {
    'napoleonic': {
        'name': 'Отечественная война 1812',
        'start': 1812,
        'end': 1814,
        'conscription_age': (18, 45)
    },
    'crimean': {
        'name': 'Крымская война',
        'start': 1853,
        'end': 1856,
        'conscription_age': (20, 43)
    },
    'russo_turkish': {
        'name': 'Русско-турецкая война',
        'start': 1877,
        'end': 1878,
        'conscription_age': (21, 43)
    },
    'russo_japanese': {
        'name': 'Русско-японская война',
        'start': 1904,
        'end': 1905,
        'conscription_age': (21, 43)
    },
    'ww1': {
        'name': 'Первая мировая война',
        'start': 1914,
        'end': 1918,
        'conscription_age': (18, 43)
    },
    'civil': {
        'name': 'Гражданская война',
        'start': 1918,
        'end': 1922,
        'conscription_age': (18, 50)
    },
    'ww2': {
        'name': 'Великая Отечественная война',
        'start': 1941,
        'end': 1945,
        'conscription_age': (17, 55)
    },
    'afghan': {
        'name': 'Афганская война',
        'start': 1979,
        'end': 1989,
        'conscription_age': (18, 27)
    }
}


@dataclass
class WarCasualty:
    """Данные о потенциальной жертве войны."""
    person: Person
    war: str
    war_name: str
    death_year: int
    birth_year: Optional[int]
    age_at_death: Optional[int]
    in_conscription_age: bool
    cause_of_death: Optional[str]


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def get_death_year(person: Person) -> Optional[int]:
    """Получить год смерти."""
    if person.death_date:
        return person.death_date.year
    return person.death_year


def get_cause_of_death(person: Person) -> Optional[str]:
    """Получить причину смерти."""
    if hasattr(person, 'death_cause') and person.death_cause:
        return person.death_cause

    # Проверяем notes
    if hasattr(person, 'notes') and person.notes:
        notes = person.notes if isinstance(person.notes, list) else [person.notes]
        for note in notes:
            if note:
                note_lower = note.lower()
                if any(w in note_lower for w in ['погиб', 'убит', 'война', 'фронт', 'бой']):
                    return note

    return None


def analyze_war_casualties(data: GedcomData, war_code: Optional[str] = None) -> Dict:
    """Анализ потерь в войнах."""
    stats = {
        'total_persons': 0,
        'total_deaths': 0,
        'war_period_deaths': defaultdict(list),
        'by_war': {},
        'male_deaths_by_year': defaultdict(int),
        'female_deaths_by_year': defaultdict(int),
        'births_by_year': defaultdict(int),
        'marriages_by_year': defaultdict(int),
        'sex_ratio_at_birth': defaultdict(lambda: {'M': 0, 'F': 0}),
        'widows_created': defaultdict(int)
    }

    # Фильтруем войны
    wars_to_analyze = WARS
    if war_code and war_code in WARS:
        wars_to_analyze = {war_code: WARS[war_code]}

    # Инициализируем статистику по войнам
    for code, war in wars_to_analyze.items():
        stats['by_war'][code] = {
            'name': war['name'],
            'start': war['start'],
            'end': war['end'],
            'casualties': [],
            'male_deaths': 0,
            'female_deaths': 0,
            'conscription_age_deaths': 0,
            'total_deaths': 0
        }

    # Анализируем персоны
    for person_id, person in data.persons.items():
        stats['total_persons'] += 1

        birth_year = get_birth_year(person)
        death_year = get_death_year(person)

        # Рождения по годам
        if birth_year:
            stats['births_by_year'][birth_year] += 1
            if person.sex:
                stats['sex_ratio_at_birth'][birth_year][person.sex] += 1

        if not death_year:
            continue

        stats['total_deaths'] += 1

        # Смерти по полу и году
        if person.sex == 'M':
            stats['male_deaths_by_year'][death_year] += 1
        elif person.sex == 'F':
            stats['female_deaths_by_year'][death_year] += 1

        # Проверяем каждую войну
        for code, war in wars_to_analyze.items():
            if war['start'] <= death_year <= war['end']:
                age_at_death = None
                if birth_year:
                    age_at_death = death_year - birth_year

                # Проверяем призывной возраст
                in_conscription = False
                if age_at_death and person.sex == 'M':
                    min_age, max_age = war['conscription_age']
                    in_conscription = min_age <= age_at_death <= max_age

                cause = get_cause_of_death(person)

                casualty = WarCasualty(
                    person=person,
                    war=code,
                    war_name=war['name'],
                    death_year=death_year,
                    birth_year=birth_year,
                    age_at_death=age_at_death,
                    in_conscription_age=in_conscription,
                    cause_of_death=cause
                )

                stats['by_war'][code]['casualties'].append(casualty)
                stats['by_war'][code]['total_deaths'] += 1

                if person.sex == 'M':
                    stats['by_war'][code]['male_deaths'] += 1
                    if in_conscription:
                        stats['by_war'][code]['conscription_age_deaths'] += 1
                elif person.sex == 'F':
                    stats['by_war'][code]['female_deaths'] += 1

    # Браки по годам
    for family_id, family in data.families.items():
        if family.marriage_date:
            stats['marriages_by_year'][family.marriage_date.year] += 1
        elif family.marriage_year:
            stats['marriages_by_year'][family.marriage_year] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ влияния войн на демографию'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--war', metavar='CODE',
                        choices=list(WARS.keys()),
                        help=f'Анализировать конкретную войну: {", ".join(WARS.keys())}')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ВЛИЯНИЯ ВОЙН НА ДЕМОГРАФИЮ")
    output_lines.append("=" * 100)

    stats = analyze_war_casualties(data, args.war)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего персон: {stats['total_persons']}")
    output_lines.append(f"   Всего смертей с датами: {stats['total_deaths']}")

    # По каждой войне
    for code, war_stats in stats['by_war'].items():
        if war_stats['total_deaths'] == 0:
            continue

        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"⚔️ {war_stats['name'].upper()} ({war_stats['start']}-{war_stats['end']})")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   Смертей в период войны: {war_stats['total_deaths']}")
        output_lines.append(f"   Мужчин: {war_stats['male_deaths']}")
        output_lines.append(f"   Женщин: {war_stats['female_deaths']}")

        if war_stats['male_deaths'] > 0:
            consc_pct = war_stats['conscription_age_deaths'] / war_stats['male_deaths'] * 100
            output_lines.append(f"   Мужчин призывного возраста: {war_stats['conscription_age_deaths']} ({consc_pct:.1f}%)")

        # Список погибших
        casualties = war_stats['casualties']
        if casualties:
            # Сортируем: сначала мужчины призывного возраста
            sorted_casualties = sorted(casualties,
                key=lambda x: (not x.in_conscription_age, x.death_year, x.person.name))

            output_lines.append(f"\n   📋 Погибшие ({len(casualties)}):")

            for c in sorted_casualties[:30]:
                sex_icon = "👨" if c.person.sex == 'M' else "👩" if c.person.sex == 'F' else "👤"
                age_str = f", {c.age_at_death} лет" if c.age_at_death else ""
                conscr_str = " [призывной возраст]" if c.in_conscription_age else ""
                cause_str = f" - {c.cause_of_death[:50]}..." if c.cause_of_death else ""

                output_lines.append(f"      {sex_icon} {c.person.name} (†{c.death_year}{age_str}){conscr_str}{cause_str}")

            if len(casualties) > 30:
                output_lines.append(f"      ... и ещё {len(casualties) - 30} человек")

        # Анализ до/после войны
        start = war_stats['start']
        end = war_stats['end']

        # Смерти до, во время и после
        pre_war_years = range(start - 5, start)
        war_years = range(start, end + 1)
        post_war_years = range(end + 1, end + 6)

        pre_male_deaths = sum(stats['male_deaths_by_year'].get(y, 0) for y in pre_war_years)
        war_male_deaths = sum(stats['male_deaths_by_year'].get(y, 0) for y in war_years)
        post_male_deaths = sum(stats['male_deaths_by_year'].get(y, 0) for y in post_war_years)

        if pre_male_deaths > 0 or war_male_deaths > 0:
            output_lines.append(f"\n   📈 Динамика мужских смертей:")
            output_lines.append(f"      5 лет до войны ({start-5}-{start-1}): {pre_male_deaths}")
            output_lines.append(f"      Во время войны ({start}-{end}): {war_male_deaths}")
            output_lines.append(f"      5 лет после войны ({end+1}-{end+5}): {post_male_deaths}")

        # Рождаемость
        pre_births = sum(stats['births_by_year'].get(y, 0) for y in pre_war_years)
        war_births = sum(stats['births_by_year'].get(y, 0) for y in war_years)
        post_births = sum(stats['births_by_year'].get(y, 0) for y in post_war_years)

        if pre_births > 0 or war_births > 0:
            output_lines.append(f"\n   👶 Динамика рождений:")
            output_lines.append(f"      5 лет до войны: {pre_births}")
            output_lines.append(f"      Во время войны: {war_births}")
            output_lines.append(f"      5 лет после войны: {post_births}")

        # Браки
        pre_marriages = sum(stats['marriages_by_year'].get(y, 0) for y in pre_war_years)
        war_marriages = sum(stats['marriages_by_year'].get(y, 0) for y in war_years)
        post_marriages = sum(stats['marriages_by_year'].get(y, 0) for y in post_war_years)

        if pre_marriages > 0 or war_marriages > 0:
            output_lines.append(f"\n   💒 Динамика браков:")
            output_lines.append(f"      5 лет до войны: {pre_marriages}")
            output_lines.append(f"      Во время войны: {war_marriages}")
            output_lines.append(f"      5 лет после войны: {post_marriages}")

    # Сводная таблица по всем войнам
    wars_with_casualties = [(c, s) for c, s in stats['by_war'].items() if s['total_deaths'] > 0]
    if len(wars_with_casualties) > 1:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📊 СВОДНАЯ ТАБЛИЦА")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   {'Война':<35} {'Период':<12} {'Всего':<8} {'Муж.':<8} {'Призывн.':<10}")
        output_lines.append("   " + "-" * 80)

        for code, war_stats in sorted(wars_with_casualties, key=lambda x: x[1]['start']):
            period = f"{war_stats['start']}-{war_stats['end']}"
            output_lines.append(f"   {war_stats['name']:<35} {period:<12} "
                              f"{war_stats['total_deaths']:<8} {war_stats['male_deaths']:<8} "
                              f"{war_stats['conscription_age_deaths']:<10}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Влияние войн на демографию:

   📉 Прямые потери:
   • Гибель мужчин призывного возраста
   • Смерти от болезней, голода, репрессий

   📉 Косвенные последствия:
   • Снижение рождаемости во время и после войны
   • Рост числа вдов и сирот
   • Нарушение соотношения полов (дефицит мужчин)
   • «Эхо войны» — снижение рождаемости через ~25 лет

   📈 Компенсаторные эффекты:
   • Бум рождаемости через 1-2 года после войны
   • Рост числа браков после демобилизации

   Особенности войн:
   • ВОВ (1941-45) — наибольшие потери в истории России
   • Гражданская война — потери от голода и репрессий
   • ПМВ — большие потери, переход в революцию

   ⚠️ Данные неполны: многие погибшие не записаны,
   даты смерти часто отсутствуют или приблизительны.
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
