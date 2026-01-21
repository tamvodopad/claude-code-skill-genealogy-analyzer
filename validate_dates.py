#!/usr/bin/env python3
"""
Детектор аномалий дат в GEDCOM файле.
Находит логические несоответствия в датах рождений, смертей и браков.

Использование:
    python3 validate_dates.py tree.ged
    python3 validate_dates.py tree.ged --before 1920  # только до 1920 года
"""

import sys
import argparse
from dataclasses import dataclass, field
from typing import List, Optional
from collections import defaultdict

# Добавляем lib в путь
sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class Anomaly:
    """Аномалия в данных."""
    severity: str  # critical, warning, info
    category: str
    person_id: str
    person_name: str
    description: str
    details: str = ""


def year_or_date_year(person: Person, attr: str) -> Optional[int]:
    """Получить год из даты или year-поля."""
    date_val = getattr(person, f"{attr}_date", None)
    if date_val:
        return date_val.year
    return getattr(person, f"{attr}_year", None)


def validate_individual(person: Person, data: GedcomData) -> List[Anomaly]:
    """Проверка отдельной персоны на аномалии."""
    anomalies = []

    birth_year = year_or_date_year(person, "birth")
    death_year = year_or_date_year(person, "death")

    # 1. Смерть до рождения
    if birth_year and death_year and death_year < birth_year:
        anomalies.append(Anomaly(
            severity="critical",
            category="Смерть до рождения",
            person_id=person.id,
            person_name=person.name,
            description=f"Смерть ({death_year}) раньше рождения ({birth_year})",
            details=f"Разница: {birth_year - death_year} лет"
        ))

    # 2. Неправдоподобный возраст смерти
    if birth_year and death_year:
        age = death_year - birth_year
        if age > 120:
            anomalies.append(Anomaly(
                severity="warning",
                category="Неправдоподобный возраст",
                person_id=person.id,
                person_name=person.name,
                description=f"Возраст на момент смерти: {age} лет",
                details=f"Рождение: {birth_year}, Смерть: {death_year}"
            ))
        elif age < 0:
            anomalies.append(Anomaly(
                severity="critical",
                category="Отрицательный возраст",
                person_id=person.id,
                person_name=person.name,
                description=f"Отрицательный возраст: {age}",
                details=f"Рождение: {birth_year}, Смерть: {death_year}"
            ))

    # 3. Рождение до родителей или после смерти родителей
    father, mother = data.get_parents(person)

    if father and birth_year:
        father_birth = year_or_date_year(father, "birth")
        father_death = year_or_date_year(father, "death")

        if father_birth and birth_year < father_birth:
            anomalies.append(Anomaly(
                severity="critical",
                category="Рождение до рождения отца",
                person_id=person.id,
                person_name=person.name,
                description=f"Родился ({birth_year}) до рождения отца ({father_birth})",
                details=f"Отец: {father.name}"
            ))

        if father_birth and birth_year - father_birth < 12:
            anomalies.append(Anomaly(
                severity="warning",
                category="Слишком молодой отец",
                person_id=person.id,
                person_name=person.name,
                description=f"Отцу было {birth_year - father_birth} лет при рождении ребёнка",
                details=f"Отец: {father.name} ({father_birth})"
            ))

        if father_birth and birth_year - father_birth > 80:
            anomalies.append(Anomaly(
                severity="warning",
                category="Слишком старый отец",
                person_id=person.id,
                person_name=person.name,
                description=f"Отцу было {birth_year - father_birth} лет при рождении ребёнка",
                details=f"Отец: {father.name} ({father_birth})"
            ))

        # Рождение более чем через 9 месяцев после смерти отца
        if father_death and birth_year > father_death:
            # Проверяем точные даты если есть
            if person.birth_date and father.death_date:
                days_diff = (person.birth_date - father.death_date).days
                if days_diff > 280:  # ~9 месяцев
                    anomalies.append(Anomaly(
                        severity="critical",
                        category="Рождение после смерти отца",
                        person_id=person.id,
                        person_name=person.name,
                        description=f"Родился через {days_diff} дней после смерти отца",
                        details=f"Отец: {father.name}, умер: {father.death_date}"
                    ))
            elif birth_year > father_death + 1:
                anomalies.append(Anomaly(
                    severity="critical",
                    category="Рождение после смерти отца",
                    person_id=person.id,
                    person_name=person.name,
                    description=f"Родился ({birth_year}) более чем через год после смерти отца ({father_death})",
                    details=f"Отец: {father.name}"
                ))

    if mother and birth_year:
        mother_birth = year_or_date_year(mother, "birth")
        mother_death = year_or_date_year(mother, "death")

        if mother_birth and birth_year < mother_birth:
            anomalies.append(Anomaly(
                severity="critical",
                category="Рождение до рождения матери",
                person_id=person.id,
                person_name=person.name,
                description=f"Родился ({birth_year}) до рождения матери ({mother_birth})",
                details=f"Мать: {mother.name}"
            ))

        if mother_birth and birth_year - mother_birth < 12:
            anomalies.append(Anomaly(
                severity="warning",
                category="Слишком молодая мать",
                person_id=person.id,
                person_name=person.name,
                description=f"Матери было {birth_year - mother_birth} лет при рождении ребёнка",
                details=f"Мать: {mother.name} ({mother_birth})"
            ))

        if mother_birth and birth_year - mother_birth > 55:
            anomalies.append(Anomaly(
                severity="warning",
                category="Слишком старая мать",
                person_id=person.id,
                person_name=person.name,
                description=f"Матери было {birth_year - mother_birth} лет при рождении ребёнка",
                details=f"Мать: {mother.name} ({mother_birth})"
            ))

        if mother_death and birth_year > mother_death:
            anomalies.append(Anomaly(
                severity="critical",
                category="Рождение после смерти матери",
                person_id=person.id,
                person_name=person.name,
                description=f"Родился ({birth_year}) после смерти матери ({mother_death})",
                details=f"Мать: {mother.name}"
            ))

    return anomalies


def validate_family(family: Family, data: GedcomData) -> List[Anomaly]:
    """Проверка семьи на аномалии."""
    anomalies = []

    husband = data.get_person(family.husband_id) if family.husband_id else None
    wife = data.get_person(family.wife_id) if family.wife_id else None

    marriage_year = family.marriage_year
    if family.marriage_date:
        marriage_year = family.marriage_date.year

    # 1. Брак до рождения супругов
    if husband and marriage_year:
        husband_birth = year_or_date_year(husband, "birth")
        if husband_birth and marriage_year < husband_birth:
            anomalies.append(Anomaly(
                severity="critical",
                category="Брак до рождения",
                person_id=husband.id,
                person_name=husband.name,
                description=f"Брак ({marriage_year}) до рождения мужа ({husband_birth})",
                details=f"Семья: {family.id}"
            ))
        elif husband_birth and marriage_year - husband_birth < 14:
            anomalies.append(Anomaly(
                severity="warning",
                category="Ранний брак",
                person_id=husband.id,
                person_name=husband.name,
                description=f"Мужу было {marriage_year - husband_birth} лет при браке",
                details=f"Семья: {family.id}, год брака: {marriage_year}"
            ))

    if wife and marriage_year:
        wife_birth = year_or_date_year(wife, "birth")
        if wife_birth and marriage_year < wife_birth:
            anomalies.append(Anomaly(
                severity="critical",
                category="Брак до рождения",
                person_id=wife.id,
                person_name=wife.name,
                description=f"Брак ({marriage_year}) до рождения жены ({wife_birth})",
                details=f"Семья: {family.id}"
            ))
        elif wife_birth and marriage_year - wife_birth < 12:
            anomalies.append(Anomaly(
                severity="warning",
                category="Ранний брак",
                person_id=wife.id,
                person_name=wife.name,
                description=f"Жене было {marriage_year - wife_birth} лет при браке",
                details=f"Семья: {family.id}, год брака: {marriage_year}"
            ))

    # 2. Брак после смерти супругов
    if husband and marriage_year:
        husband_death = year_or_date_year(husband, "death")
        if husband_death and marriage_year > husband_death:
            anomalies.append(Anomaly(
                severity="critical",
                category="Брак после смерти",
                person_id=husband.id,
                person_name=husband.name,
                description=f"Брак ({marriage_year}) после смерти мужа ({husband_death})",
                details=f"Семья: {family.id}"
            ))

    if wife and marriage_year:
        wife_death = year_or_date_year(wife, "death")
        if wife_death and marriage_year > wife_death:
            anomalies.append(Anomaly(
                severity="critical",
                category="Брак после смерти",
                person_id=wife.id,
                person_name=wife.name,
                description=f"Брак ({marriage_year}) после смерти жены ({wife_death})",
                details=f"Семья: {family.id}"
            ))

    # 3. Большая разница в возрасте супругов
    if husband and wife:
        husband_birth = year_or_date_year(husband, "birth")
        wife_birth = year_or_date_year(wife, "birth")
        if husband_birth and wife_birth:
            age_diff = abs(husband_birth - wife_birth)
            if age_diff > 30:
                older = husband.name if husband_birth < wife_birth else wife.name
                younger = wife.name if husband_birth < wife_birth else husband.name
                anomalies.append(Anomaly(
                    severity="info",
                    category="Большая разница в возрасте",
                    person_id=family.id,
                    person_name=f"{husband.name} & {wife.name}",
                    description=f"Разница в возрасте супругов: {age_diff} лет",
                    details=f"{older} старше {younger}"
                ))

    # 4. Дети рождены до брака (только для браков с точной датой)
    if marriage_year:
        for child_id in family.children_ids:
            child = data.get_person(child_id)
            if child:
                child_birth = year_or_date_year(child, "birth")
                if child_birth and child_birth < marriage_year:
                    # Проверяем точные даты если есть
                    if child.birth_date and family.marriage_date:
                        days_before = (family.marriage_date - child.birth_date).days
                        if days_before > 0:
                            anomalies.append(Anomaly(
                                severity="info",
                                category="Ребёнок до брака",
                                person_id=child.id,
                                person_name=child.name,
                                description=f"Родился за {days_before} дней до брака родителей",
                                details=f"Рождение: {child.birth_date}, Брак: {family.marriage_date}"
                            ))
                    elif child_birth < marriage_year:
                        anomalies.append(Anomaly(
                            severity="info",
                            category="Ребёнок до брака",
                            person_id=child.id,
                            person_name=child.name,
                            description=f"Родился ({child_birth}) до брака родителей ({marriage_year})",
                            details=f"Семья: {family.id}"
                        ))

    return anomalies


def validate_gedcom(data: GedcomData, before_year: Optional[int] = None) -> List[Anomaly]:
    """Полная валидация GEDCOM данных."""
    anomalies = []

    # Валидация персон
    for person_id, person in data.persons.items():
        # Фильтр по году
        if before_year:
            birth_year = year_or_date_year(person, "birth")
            death_year = year_or_date_year(person, "death")
            if birth_year and birth_year > before_year:
                continue
            if not birth_year and death_year and death_year > before_year:
                continue

        person_anomalies = validate_individual(person, data)
        anomalies.extend(person_anomalies)

    # Валидация семей
    for family_id, family in data.families.items():
        # Фильтр по году
        if before_year:
            marriage_year = family.marriage_year
            if family.marriage_date:
                marriage_year = family.marriage_date.year
            if marriage_year and marriage_year > before_year:
                continue

        family_anomalies = validate_family(family, data)
        anomalies.extend(family_anomalies)

    return anomalies


def main():
    parser = argparse.ArgumentParser(
        description='Детектор аномалий дат в GEDCOM файле'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Анализировать только записи до указанного года')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    anomalies = validate_gedcom(data, args.before)

    # Группировка по severity
    by_severity = defaultdict(list)
    for a in anomalies:
        by_severity[a.severity].append(a)

    # Группировка по категории
    by_category = defaultdict(list)
    for a in anomalies:
        by_category[a.category].append(a)

    # Формируем отчёт
    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("ОТЧЁТ О ВАЛИДАЦИИ ДАТА В GEDCOM ФАЙЛЕ")
    if args.before:
        output_lines.append(f"(только записи до {args.before} года)")
    output_lines.append("=" * 100)

    output_lines.append(f"\nВсего найдено аномалий: {len(anomalies)}")
    output_lines.append(f"  🔴 Критические: {len(by_severity['critical'])}")
    output_lines.append(f"  🟡 Предупреждения: {len(by_severity['warning'])}")
    output_lines.append(f"  🔵 Информация: {len(by_severity['info'])}")

    # Критические
    if by_severity['critical']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🔴 КРИТИЧЕСКИЕ АНОМАЛИИ")
        output_lines.append("=" * 100)

        for cat in sorted(set(a.category for a in by_severity['critical'])):
            cat_anomalies = [a for a in by_severity['critical'] if a.category == cat]
            output_lines.append(f"\n📌 {cat} ({len(cat_anomalies)}):")
            for a in cat_anomalies:
                output_lines.append(f"   • {a.person_name}: {a.description}")
                if a.details:
                    output_lines.append(f"     └─ {a.details}")

    # Предупреждения
    if by_severity['warning']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🟡 ПРЕДУПРЕЖДЕНИЯ")
        output_lines.append("=" * 100)

        for cat in sorted(set(a.category for a in by_severity['warning'])):
            cat_anomalies = [a for a in by_severity['warning'] if a.category == cat]
            output_lines.append(f"\n📌 {cat} ({len(cat_anomalies)}):")
            for a in cat_anomalies:
                output_lines.append(f"   • {a.person_name}: {a.description}")
                if a.details:
                    output_lines.append(f"     └─ {a.details}")

    # Информация
    if by_severity['info']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🔵 ИНФОРМАЦИЯ")
        output_lines.append("=" * 100)

        for cat in sorted(set(a.category for a in by_severity['info'])):
            cat_anomalies = [a for a in by_severity['info'] if a.category == cat]
            output_lines.append(f"\n📌 {cat} ({len(cat_anomalies)}):")
            for a in cat_anomalies[:20]:  # Ограничиваем вывод
                output_lines.append(f"   • {a.person_name}: {a.description}")
                if a.details:
                    output_lines.append(f"     └─ {a.details}")
            if len(cat_anomalies) > 20:
                output_lines.append(f"   ... и ещё {len(cat_anomalies) - 20} записей")

    output_lines.append("\n" + "=" * 100)
    output_lines.append("СВОДКА ПО КАТЕГОРИЯМ")
    output_lines.append("=" * 100)
    for cat in sorted(by_category.keys()):
        count = len(by_category[cat])
        output_lines.append(f"  {cat}: {count}")

    # Вывод
    report = "\n".join(output_lines)
    print(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n💾 Отчёт сохранён в: {args.output}")


if __name__ == '__main__':
    main()
