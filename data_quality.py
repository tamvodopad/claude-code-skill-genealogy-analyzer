#!/usr/bin/env python3
"""
Анализ качества данных в GEDCOM файле.
Вычисляет метрики полноты и качества генеалогических данных.

Использование:
    python3 data_quality.py tree.ged
    python3 data_quality.py tree.ged --by-century  # разбивка по векам
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class PersonQualityScore:
    """Оценка качества данных о персоне."""
    person: Person
    score: int  # 0-100
    has_birth_date: bool
    has_birth_place: bool
    has_death_date: bool
    has_death_place: bool
    has_parents: bool
    has_spouse: bool
    has_children: bool
    has_occupation: bool
    has_notes: bool
    missing_fields: List[str]


def get_person_century(person: Person) -> Optional[int]:
    """Определение века жизни персоны."""
    year = None
    if person.birth_year:
        year = person.birth_year
    elif person.birth_date:
        year = person.birth_date.year
    elif person.death_year:
        year = person.death_year
    elif person.death_date:
        year = person.death_date.year

    if year:
        return (year - 1) // 100 + 1
    return None


def calculate_person_quality(person: Person, data: GedcomData) -> PersonQualityScore:
    """Вычисление качества данных о персоне."""
    # Веса для разных полей
    weights = {
        'birth_date': 15,
        'birth_year': 10,
        'birth_place': 10,
        'death_date': 10,
        'death_year': 7,
        'death_place': 7,
        'given_name': 8,
        'surname': 8,
        'sex': 5,
        'parents': 10,
        'spouse': 5,
        'children': 3,
        'occupation': 5,
        'notes': 2,
    }

    score = 0
    missing = []

    # Имя
    if person.given_name:
        score += weights['given_name']
    else:
        missing.append("имя")

    if person.surname:
        score += weights['surname']
    else:
        missing.append("фамилия")

    # Пол
    if person.sex:
        score += weights['sex']
    else:
        missing.append("пол")

    # Даты рождения
    has_birth_date = False
    if person.birth_date:
        score += weights['birth_date']
        has_birth_date = True
    elif person.birth_year:
        score += weights['birth_year']
    else:
        missing.append("дата рождения")

    # Место рождения
    has_birth_place = bool(person.birth_place)
    if has_birth_place:
        score += weights['birth_place']
    else:
        missing.append("место рождения")

    # Даты смерти (если человек умер)
    has_death_date = False
    if person.death_date:
        score += weights['death_date']
        has_death_date = True
    elif person.death_year:
        score += weights['death_year']
    # Не штрафуем за отсутствие даты смерти — человек может быть жив

    # Место смерти
    has_death_place = bool(person.death_place)
    if has_death_place:
        score += weights['death_place']

    # Родители
    father, mother = data.get_parents(person)
    has_parents = father is not None or mother is not None
    if has_parents:
        score += weights['parents']
    else:
        missing.append("родители")

    # Супруг
    spouses = data.get_spouses(person)
    has_spouse = len(spouses) > 0
    if has_spouse:
        score += weights['spouse']

    # Дети
    children = data.get_children(person)
    has_children = len(children) > 0
    if has_children:
        score += weights['children']

    # Занятие
    has_occupation = bool(person.occupation)
    if has_occupation:
        score += weights['occupation']

    # Заметки
    has_notes = len(person.notes) > 0
    if has_notes:
        score += weights['notes']

    return PersonQualityScore(
        person=person,
        score=score,
        has_birth_date=has_birth_date,
        has_birth_place=has_birth_place,
        has_death_date=has_death_date,
        has_death_place=has_death_place,
        has_parents=has_parents,
        has_spouse=has_spouse,
        has_children=has_children,
        has_occupation=has_occupation,
        has_notes=has_notes,
        missing_fields=missing
    )


def calculate_family_completeness(data: GedcomData) -> Dict:
    """Анализ полноты данных о семьях."""
    stats = {
        'total': len(data.families),
        'with_both_spouses': 0,
        'with_marriage_date': 0,
        'with_marriage_place': 0,
        'with_children': 0,
        'avg_children': 0,
    }

    total_children = 0
    families_with_children = 0

    for family in data.families.values():
        if family.husband_id and family.wife_id:
            stats['with_both_spouses'] += 1

        if family.marriage_date or family.marriage_year:
            stats['with_marriage_date'] += 1

        if family.marriage_place:
            stats['with_marriage_place'] += 1

        if family.children_ids:
            stats['with_children'] += 1
            families_with_children += 1
            total_children += len(family.children_ids)

    if families_with_children > 0:
        stats['avg_children'] = total_children / families_with_children

    return stats


def analyze_quality(data: GedcomData, by_century: bool = False) -> Tuple[List[PersonQualityScore], Dict, Dict]:
    """Полный анализ качества данных."""

    # Оценка каждой персоны
    person_scores = []
    for person in data.persons.values():
        score = calculate_person_quality(person, data)
        person_scores.append(score)

    # Общая статистика
    total = len(person_scores)
    stats = {
        'total_persons': total,
        'avg_score': sum(s.score for s in person_scores) / total if total > 0 else 0,
        'with_birth_date': sum(1 for s in person_scores if s.has_birth_date),
        'with_birth_year': sum(1 for s in person_scores if s.person.birth_year or s.person.birth_date),
        'with_birth_place': sum(1 for s in person_scores if s.has_birth_place),
        'with_death_date': sum(1 for s in person_scores if s.has_death_date),
        'with_death_place': sum(1 for s in person_scores if s.has_death_place),
        'with_parents': sum(1 for s in person_scores if s.has_parents),
        'with_occupation': sum(1 for s in person_scores if s.has_occupation),
        'with_notes': sum(1 for s in person_scores if s.has_notes),
    }

    # Распределение по качеству
    quality_dist = {
        'excellent': sum(1 for s in person_scores if s.score >= 80),
        'good': sum(1 for s in person_scores if 60 <= s.score < 80),
        'fair': sum(1 for s in person_scores if 40 <= s.score < 60),
        'poor': sum(1 for s in person_scores if 20 <= s.score < 40),
        'minimal': sum(1 for s in person_scores if s.score < 20),
    }
    stats['quality_distribution'] = quality_dist

    # Анализ по векам
    century_stats = {}
    if by_century:
        by_century_scores = defaultdict(list)
        for score in person_scores:
            century = get_person_century(score.person)
            if century:
                by_century_scores[century].append(score)

        for century, scores in by_century_scores.items():
            century_total = len(scores)
            century_stats[century] = {
                'count': century_total,
                'avg_score': sum(s.score for s in scores) / century_total,
                'with_birth_date_pct': 100 * sum(1 for s in scores if s.has_birth_date) / century_total,
                'with_birth_place_pct': 100 * sum(1 for s in scores if s.has_birth_place) / century_total,
                'with_parents_pct': 100 * sum(1 for s in scores if s.has_parents) / century_total,
            }

    return person_scores, stats, century_stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ качества данных в GEDCOM файле'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--by-century', action='store_true',
                        help='Показать статистику по векам')
    parser.add_argument('--show-worst', type=int, metavar='N', default=0,
                        help='Показать N персон с худшим качеством данных')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    person_scores, stats, century_stats = analyze_quality(data, args.by_century)
    family_stats = calculate_family_completeness(data)

    # Формируем отчёт
    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("ОТЧЁТ О КАЧЕСТВЕ ДАННЫХ В GEDCOM ФАЙЛЕ")
    output_lines.append("=" * 100)

    # Общая оценка
    avg = stats['avg_score']
    if avg >= 80:
        grade = "🏆 ОТЛИЧНО"
    elif avg >= 60:
        grade = "✅ ХОРОШО"
    elif avg >= 40:
        grade = "⚠️ УДОВЛЕТВОРИТЕЛЬНО"
    else:
        grade = "❌ ТРЕБУЕТ УЛУЧШЕНИЯ"

    output_lines.append(f"\n📊 ОБЩАЯ ОЦЕНКА КАЧЕСТВА: {grade}")
    output_lines.append(f"   Средний балл: {avg:.1f}/100")

    # Распределение по качеству
    dist = stats['quality_distribution']
    output_lines.append("\n📈 РАСПРЕДЕЛЕНИЕ ПО КАЧЕСТВУ:")
    total = stats['total_persons']

    def pct(n):
        return 100 * n / total if total > 0 else 0

    def bar(n, max_len=30):
        length = int(max_len * n / total) if total > 0 else 0
        return "█" * length

    output_lines.append(f"   Отлично (80-100):     {bar(dist['excellent'])} {dist['excellent']} ({pct(dist['excellent']):.1f}%)")
    output_lines.append(f"   Хорошо (60-79):       {bar(dist['good'])} {dist['good']} ({pct(dist['good']):.1f}%)")
    output_lines.append(f"   Удовл. (40-59):       {bar(dist['fair'])} {dist['fair']} ({pct(dist['fair']):.1f}%)")
    output_lines.append(f"   Плохо (20-39):        {bar(dist['poor'])} {dist['poor']} ({pct(dist['poor']):.1f}%)")
    output_lines.append(f"   Минимально (0-19):    {bar(dist['minimal'])} {dist['minimal']} ({pct(dist['minimal']):.1f}%)")

    # Полнота данных о персонах
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📋 ПОЛНОТА ДАННЫХ О ПЕРСОНАХ")
    output_lines.append("=" * 100)

    fields = [
        ('Год рождения', stats['with_birth_year']),
        ('Точная дата рождения', stats['with_birth_date']),
        ('Место рождения', stats['with_birth_place']),
        ('Точная дата смерти', stats['with_death_date']),
        ('Место смерти', stats['with_death_place']),
        ('Известные родители', stats['with_parents']),
        ('Занятие/профессия', stats['with_occupation']),
        ('Заметки', stats['with_notes']),
    ]

    max_label = max(len(f[0]) for f in fields)
    for label, count in fields:
        p = pct(count)
        b = bar(count)
        output_lines.append(f"   {label.ljust(max_label)}: {b} {count} ({p:.1f}%)")

    # Полнота данных о семьях
    output_lines.append("\n" + "=" * 100)
    output_lines.append("👨‍👩‍👧‍👦 ПОЛНОТА ДАННЫХ О СЕМЬЯХ")
    output_lines.append("=" * 100)

    fam_total = family_stats['total']

    def fam_pct(n):
        return 100 * n / fam_total if fam_total > 0 else 0

    output_lines.append(f"   Всего семей: {fam_total}")
    output_lines.append(f"   Оба супруга указаны: {family_stats['with_both_spouses']} ({fam_pct(family_stats['with_both_spouses']):.1f}%)")
    output_lines.append(f"   Дата брака указана: {family_stats['with_marriage_date']} ({fam_pct(family_stats['with_marriage_date']):.1f}%)")
    output_lines.append(f"   Место брака указано: {family_stats['with_marriage_place']} ({fam_pct(family_stats['with_marriage_place']):.1f}%)")
    output_lines.append(f"   Есть дети: {family_stats['with_children']} ({fam_pct(family_stats['with_children']):.1f}%)")
    output_lines.append(f"   Среднее число детей: {family_stats['avg_children']:.1f}")

    # По векам
    if century_stats:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 КАЧЕСТВО ДАННЫХ ПО ВЕКАМ")
        output_lines.append("=" * 100)

        for century in sorted(century_stats.keys()):
            cs = century_stats[century]
            output_lines.append(f"\n   {century} век ({cs['count']} персон):")
            output_lines.append(f"      Средний балл: {cs['avg_score']:.1f}")
            output_lines.append(f"      С датой рождения: {cs['with_birth_date_pct']:.1f}%")
            output_lines.append(f"      С местом рождения: {cs['with_birth_place_pct']:.1f}%")
            output_lines.append(f"      С известными родителями: {cs['with_parents_pct']:.1f}%")

    # Худшие записи
    if args.show_worst > 0:
        output_lines.append("\n" + "=" * 100)
        output_lines.append(f"⚠️ ПЕРСОНЫ С ХУДШИМ КАЧЕСТВОМ ДАННЫХ (топ {args.show_worst})")
        output_lines.append("=" * 100)

        sorted_scores = sorted(person_scores, key=lambda x: x.score)
        for ps in sorted_scores[:args.show_worst]:
            year = ps.person.birth_year or (ps.person.birth_date.year if ps.person.birth_date else "?")
            output_lines.append(f"\n   • {ps.person.name} ({year}) — балл: {ps.score}")
            if ps.missing_fields:
                output_lines.append(f"     Отсутствует: {', '.join(ps.missing_fields)}")

    # Рекомендации
    output_lines.append("\n" + "=" * 100)
    output_lines.append("💡 РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ")
    output_lines.append("=" * 100)

    recommendations = []

    if pct(stats['with_birth_date']) < 50:
        recommendations.append("📅 Уточните даты рождения — менее половины персон имеют точную дату")

    if pct(stats['with_birth_place']) < 30:
        recommendations.append("📍 Добавьте места рождения — это ключ к поиску в метрических книгах")

    if pct(stats['with_parents']) < 40:
        recommendations.append("👨‍👩‍👧 Исследуйте родительские связи — много персон без известных родителей")

    if fam_pct(family_stats['with_marriage_date']) < 50:
        recommendations.append("💒 Уточните даты браков — это поможет найти связанные записи")

    if pct(stats['with_occupation']) < 20:
        recommendations.append("💼 Добавьте занятия/профессии — это важно для понимания социального статуса")

    if not recommendations:
        recommendations.append("✨ Данные в хорошем состоянии! Продолжайте исследование.")

    for rec in recommendations:
        output_lines.append(f"   {rec}")

    # Вывод
    report = "\n".join(output_lines)
    print(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n💾 Отчёт сохранён в: {args.output}")


if __name__ == '__main__':
    main()
