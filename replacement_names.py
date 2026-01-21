#!/usr/bin/env python3
"""
Поиск «замещающих имён» в генеалогическом древе.
Традиция: если ребёнок умирал в младенчестве, следующему ребёнку того же пола
часто давали то же имя (в честь умершего).

Использование:
    python3 replacement_names.py tree.ged
    python3 replacement_names.py tree.ged --before 1920
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class ReplacementNameCase:
    """Случай замещающего имени."""
    deceased_child: Person
    replacement_child: Person
    family: Family
    deceased_age: Optional[int]  # возраст смерти в днях/годах
    time_between: Optional[int]  # дней между смертью первого и рождением второго
    confidence: str  # high, medium, low


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


def calculate_age_at_death_days(person: Person) -> Optional[int]:
    """Вычислить возраст смерти в днях (если есть точные даты)."""
    if person.birth_date and person.death_date:
        return (person.death_date - person.birth_date).days
    return None


def calculate_age_at_death_years(person: Person) -> Optional[int]:
    """Вычислить возраст смерти в годах."""
    death_year = get_death_year(person)
    birth_year = get_birth_year(person)
    if death_year and birth_year:
        return death_year - birth_year
    return None


def is_infant_death(person: Person, threshold_years: int = 5) -> bool:
    """Проверка, умер ли человек в младенчестве/детстве."""
    # Проверяем точный возраст в днях
    age_days = calculate_age_at_death_days(person)
    if age_days is not None:
        return age_days < threshold_years * 365

    # Проверяем возраст в годах
    age_years = calculate_age_at_death_years(person)
    if age_years is not None:
        return age_years < threshold_years

    # Если даты рождения и смерти в одном году — вероятно младенец
    birth_year = get_birth_year(person)
    death_year = get_death_year(person)
    if birth_year and death_year and birth_year == death_year:
        return True

    return False


def normalize_name(name: str) -> str:
    """Нормализация имени для сравнения."""
    if not name:
        return ""
    # Убираем пробелы, приводим к нижнему регистру
    n = name.strip().lower()
    # Нормализуем ё -> е
    n = n.replace('ё', 'е')
    return n


def find_replacement_names(data: GedcomData, before_year: Optional[int] = None,
                           infant_threshold: int = 5) -> Tuple[List[ReplacementNameCase], Dict]:
    """
    Поиск случаев замещающих имён.
    """
    cases = []
    stats = {
        'families_checked': 0,
        'infant_deaths_found': 0,
        'replacement_cases': 0,
        'by_confidence': {'high': 0, 'medium': 0, 'low': 0},
    }

    for family_id, family in data.families.items():
        # Фильтр по году
        if before_year:
            marriage_year = family.marriage_year
            if family.marriage_date:
                marriage_year = family.marriage_date.year
            # Если нет даты брака, проверяем по первому ребёнку
            if not marriage_year and family.children_ids:
                first_child = data.get_person(family.children_ids[0])
                if first_child:
                    marriage_year = get_birth_year(first_child)
            if marriage_year and marriage_year > before_year:
                continue

        if not family.children_ids or len(family.children_ids) < 2:
            continue

        stats['families_checked'] += 1

        # Получаем всех детей с данными
        children = []
        for child_id in family.children_ids:
            child = data.get_person(child_id)
            if child and child.given_name:
                children.append(child)

        if len(children) < 2:
            continue

        # Сортируем по году рождения
        def sort_key(p):
            if p.birth_date:
                return (p.birth_date.year, p.birth_date.month, p.birth_date.day)
            if p.birth_year:
                return (p.birth_year, 6, 15)  # середина года
            return (9999, 1, 1)

        children.sort(key=sort_key)

        # Группируем по полу
        by_sex = defaultdict(list)
        for child in children:
            if child.sex:
                by_sex[child.sex].append(child)

        # Ищем повторяющиеся имена одного пола
        for sex, sex_children in by_sex.items():
            names_seen = {}  # имя -> список детей

            for child in sex_children:
                name_norm = normalize_name(child.given_name)
                if not name_norm:
                    continue

                if name_norm in names_seen:
                    # Нашли повторяющееся имя!
                    earlier_child = names_seen[name_norm]

                    # Проверяем, умер ли предыдущий ребёнок
                    earlier_death = get_death_year(earlier_child)
                    if not earlier_death:
                        # Не знаем о смерти — может быть совпадение
                        continue

                    # Проверяем, умер ли в младенчестве
                    if not is_infant_death(earlier_child, infant_threshold):
                        continue

                    stats['infant_deaths_found'] += 1

                    # Проверяем, что второй ребёнок родился ПОСЛЕ смерти первого
                    later_birth = get_birth_year(child)
                    if later_birth and earlier_death and later_birth < earlier_death:
                        # Родился раньше смерти — не замещение
                        continue

                    # Вычисляем время между смертью и рождением
                    time_between = None
                    if earlier_child.death_date and child.birth_date:
                        time_between = (child.birth_date - earlier_child.death_date).days

                    # Определяем уверенность
                    confidence = determine_confidence(earlier_child, child, time_between)

                    stats['replacement_cases'] += 1
                    stats['by_confidence'][confidence] += 1

                    age_at_death = calculate_age_at_death_days(earlier_child)
                    if age_at_death is None:
                        age_at_death = calculate_age_at_death_years(earlier_child)
                        if age_at_death is not None:
                            age_at_death = age_at_death * 365  # примерно в днях

                    cases.append(ReplacementNameCase(
                        deceased_child=earlier_child,
                        replacement_child=child,
                        family=family,
                        deceased_age=age_at_death,
                        time_between=time_between,
                        confidence=confidence
                    ))

                # Запоминаем имя (обновляем на последнего ребёнка с этим именем)
                # Но только если этот ребёнок умер — иначе следующий уже не замещение
                death_year = get_death_year(child)
                if death_year and is_infant_death(child, infant_threshold):
                    names_seen[name_norm] = child
                elif name_norm not in names_seen:
                    names_seen[name_norm] = child

    return cases, stats


def determine_confidence(deceased: Person, replacement: Person, time_between: Optional[int]) -> str:
    """
    Определение уверенности в случае замещающего имени.
    """
    score = 0

    # Точные даты
    if deceased.death_date and replacement.birth_date:
        score += 2

    # Время между смертью и рождением
    if time_between is not None:
        if 0 < time_between < 365:  # Меньше года
            score += 2
        elif 0 < time_between < 730:  # Меньше 2 лет
            score += 1

    # Младенческая смерть
    age_days = calculate_age_at_death_days(deceased)
    if age_days is not None and age_days < 365:
        score += 2
    elif age_days is not None and age_days < 365 * 3:
        score += 1

    if score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    else:
        return "low"


def format_age(age_days: Optional[int]) -> str:
    """Форматирование возраста."""
    if age_days is None:
        return "?"

    if age_days < 30:
        return f"{age_days} дн."
    elif age_days < 365:
        months = age_days // 30
        return f"~{months} мес."
    else:
        years = age_days // 365
        return f"~{years} лет"


def main():
    parser = argparse.ArgumentParser(
        description='Поиск «замещающих имён» в генеалогическом древе'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Анализировать только записи до указанного года')
    parser.add_argument('--threshold', type=int, default=5, metavar='YEARS',
                        help='Порог возраста смерти (по умолчанию: 5 лет)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    cases, stats = find_replacement_names(data, args.before, args.threshold)

    # Формируем отчёт
    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ «ЗАМЕЩАЮЩИХ ИМЁН»")
    output_lines.append("(традиция называть ребёнка именем умершего младенца)")
    if args.before:
        output_lines.append(f"(только записи до {args.before} года)")
    output_lines.append("=" * 100)

    output_lines.append(f"\n📊 СТАТИСТИКА:")
    output_lines.append(f"   Семей проверено: {stats['families_checked']}")
    output_lines.append(f"   Найдено младенческих смертей: {stats['infant_deaths_found']}")
    output_lines.append(f"   Случаев замещающих имён: {stats['replacement_cases']}")

    output_lines.append(f"\n📈 ПО УРОВНЮ УВЕРЕННОСТИ:")
    output_lines.append(f"   🟢 Высокая: {stats['by_confidence']['high']}")
    output_lines.append(f"   🟡 Средняя: {stats['by_confidence']['medium']}")
    output_lines.append(f"   🔴 Низкая: {stats['by_confidence']['low']}")

    if cases:
        # Сортируем по уверенности
        confidence_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_cases = sorted(cases, key=lambda x: confidence_order[x.confidence])

        output_lines.append("\n" + "=" * 100)
        output_lines.append("🔄 НАЙДЕННЫЕ СЛУЧАИ ЗАМЕЩАЮЩИХ ИМЁН")
        output_lines.append("=" * 100)

        confidence_labels = {
            'high': '🟢 ВЫСОКАЯ УВЕРЕННОСТЬ',
            'medium': '🟡 СРЕДНЯЯ УВЕРЕННОСТЬ',
            'low': '🔴 НИЗКАЯ УВЕРЕННОСТЬ'
        }

        current_confidence = None
        for case in sorted_cases:
            if case.confidence != current_confidence:
                current_confidence = case.confidence
                output_lines.append(f"\n{confidence_labels[current_confidence]}:")

            deceased = case.deceased_child
            replacement = case.replacement_child

            deceased_birth = get_birth_year(deceased) or "?"
            deceased_death = get_death_year(deceased) or "?"
            replacement_birth = get_birth_year(replacement) or "?"

            age_str = format_age(case.deceased_age)

            output_lines.append(f"\n   📛 Имя: {deceased.given_name}")

            # Родители
            husband = data.get_person(case.family.husband_id) if case.family.husband_id else None
            wife = data.get_person(case.family.wife_id) if case.family.wife_id else None
            parents = []
            if husband:
                parents.append(husband.name)
            if wife:
                parents.append(wife.name)
            if parents:
                output_lines.append(f"      Родители: {' & '.join(parents)}")

            output_lines.append(f"      Умерший: {deceased.name} (род. {deceased_birth}, ум. {deceased_death}, возраст: {age_str})")
            output_lines.append(f"      Замещающий: {replacement.name} (род. {replacement_birth})")

            if case.time_between is not None:
                if case.time_between > 0:
                    output_lines.append(f"      Между смертью и рождением: {case.time_between} дней (~{case.time_between // 30} мес.)")
                else:
                    output_lines.append(f"      ⚠️ Замещающий родился ДО смерти первого ({-case.time_between} дней)")

        # Анализ по именам
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📊 САМЫЕ ЧАСТЫЕ ЗАМЕЩАЕМЫЕ ИМЕНА")
        output_lines.append("=" * 100)

        by_name = defaultdict(int)
        for case in cases:
            name = normalize_name(case.deceased_child.given_name)
            by_name[name] += 1

        sorted_names = sorted(by_name.items(), key=lambda x: -x[1])
        for name, count in sorted_names[:15]:
            output_lines.append(f"   {name.capitalize()}: {count} случаев")

        # Анализ по десятилетиям
        by_decade = defaultdict(int)
        for case in cases:
            year = get_birth_year(case.deceased_child)
            if year:
                decade = (year // 10) * 10
                by_decade[decade] += 1

        if by_decade:
            output_lines.append("\n" + "=" * 100)
            output_lines.append("📅 РАСПРЕДЕЛЕНИЕ ПО ДЕСЯТИЛЕТИЯМ")
            output_lines.append("=" * 100)

            max_count = max(by_decade.values())
            for decade in sorted(by_decade.keys()):
                count = by_decade[decade]
                bar_len = int(40 * count / max_count)
                bar = "█" * bar_len
                output_lines.append(f"   {decade}s: {bar} {count}")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Замещающие имена — распространённая традиция в России и других странах до XX века.
   При высокой детской смертности родители часто давали следующему ребёнку того же
   пола имя умершего младенца. Это могло быть связано с:

   • Желанием «сохранить» имя в семье
   • Верой в переселение души
   • Традицией называть в честь святого-покровителя
   • Ограниченным набором принятых имён в сообществе

   ⚠️ Важно: Наличие двух детей с одинаковым именем в семье НЕ всегда означает
   замещающее имя. Иногда дети с одинаковыми именами жили одновременно (редко).
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
