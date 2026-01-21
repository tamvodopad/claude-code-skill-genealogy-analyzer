#!/usr/bin/env python3
"""
Анализ профессий и социальной мобильности в генеалогическом древе.
Профессии, сословия, наследование профессий, социальная динамика.

Использование:
    python3 occupation_analysis.py tree.ged
    python3 occupation_analysis.py tree.ged --by-period
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Set, Tuple
from collections import defaultdict
import re

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


# Категории профессий
OCCUPATION_CATEGORIES = {
    'духовенство': [
        'священник', 'протоиерей', 'иерей', 'дьякон', 'диакон', 'пономарь',
        'псаломщик', 'причетник', 'архиерей', 'епископ', 'игумен', 'монах',
        'настоятель', 'протодиакон', 'архимандрит', 'митрополит', 'священнослужитель',
        'поп', 'батюшка', 'регент', 'церковнослужитель'
    ],
    'дворянство': [
        'дворянин', 'помещик', 'князь', 'граф', 'барон', 'боярин',
        'столбовой дворянин', 'потомственный дворянин', 'личный дворянин'
    ],
    'купечество': [
        'купец', 'купец 1-й гильдии', 'купец 2-й гильдии', 'купец 3-й гильдии',
        'торговец', 'промышленник', 'фабрикант', 'заводчик', 'коммерсант'
    ],
    'мещанство': [
        'мещанин', 'мещанка', 'цеховой', 'ремесленник', 'городской житель'
    ],
    'крестьянство': [
        'крестьянин', 'крестьянка', 'земледелец', 'хлебопашец',
        'государственный крестьянин', 'удельный крестьянин', 'помещичий крестьянин',
        'однодворец', 'колхозник', 'колхозница'
    ],
    'военные': [
        'солдат', 'офицер', 'унтер-офицер', 'поручик', 'капитан', 'полковник',
        'генерал', 'прапорщик', 'подпоручик', 'штабс-капитан', 'майор',
        'подполковник', 'рядовой', 'ефрейтор', 'сержант', 'старшина',
        'лейтенант', 'старший лейтенант', 'красноармеец', 'матрос', 'мичман'
    ],
    'чиновники': [
        'чиновник', 'статский советник', 'коллежский асессор', 'титулярный советник',
        'коллежский регистратор', 'губернский секретарь', 'надворный советник',
        'действительный статский советник', 'тайный советник', 'секретарь',
        'делопроизводитель', 'столоначальник', 'писец', 'писарь'
    ],
    'интеллигенция': [
        'учитель', 'учительница', 'врач', 'доктор', 'фельдшер', 'акушерка',
        'инженер', 'агроном', 'адвокат', 'присяжный поверенный', 'нотариус',
        'архитектор', 'художник', 'музыкант', 'артист', 'журналист',
        'профессор', 'доцент', 'преподаватель', 'ученый'
    ],
    'рабочие': [
        'рабочий', 'мастер', 'слесарь', 'токарь', 'кузнец', 'плотник',
        'столяр', 'маляр', 'каменщик', 'печник', 'сапожник', 'портной',
        'ткач', 'ткачиха', 'прядильщик', 'прядильщица', 'шахтер', 'горняк'
    ],
    'обслуживание': [
        'извозчик', 'дворник', 'прислуга', 'горничная', 'кухарка', 'повар',
        'лакей', 'камердинер', 'управляющий', 'приказчик', 'буфетчик'
    ]
}


@dataclass
class PersonOccupation:
    """Данные о профессии персоны."""
    person: Person
    occupation: str
    category: Optional[str]
    year: Optional[int]
    father_occupation: Optional[str]
    father_category: Optional[str]


def get_birth_year(person: Person) -> Optional[int]:
    """Получить год рождения."""
    if person.birth_date:
        return person.birth_date.year
    return person.birth_year


def normalize_occupation(occupation: str) -> str:
    """Нормализовать профессию."""
    if not occupation:
        return ""
    occ = occupation.lower().strip()
    # Убираем типичные дополнения
    occ = re.sub(r'\s+\d+-й\s+гильдии', '', occ)
    occ = re.sub(r'\s*\([^)]*\)', '', occ)
    return occ.strip()


def categorize_occupation(occupation: str) -> Optional[str]:
    """Определить категорию профессии."""
    if not occupation:
        return None

    occ_lower = occupation.lower()

    for category, keywords in OCCUPATION_CATEGORIES.items():
        for keyword in keywords:
            if keyword in occ_lower:
                return category

    return 'другое'


def get_person_occupation(person: Person) -> Optional[str]:
    """Получить профессию персоны."""
    # Профессия может быть в разных полях
    if hasattr(person, 'occupation') and person.occupation:
        return person.occupation

    # Проверяем notes на наличие профессии
    if hasattr(person, 'notes') and person.notes:
        for note in person.notes if isinstance(person.notes, list) else [person.notes]:
            if note:
                # Ищем паттерны типа "занятие:", "профессия:", "сословие:"
                match = re.search(r'(?:занятие|профессия|сословие|звание)[:\s]+([^,\n]+)', note, re.I)
                if match:
                    return match.group(1).strip()

    return None


def analyze_occupation(person: Person, data: GedcomData) -> Optional[PersonOccupation]:
    """Анализ профессии персоны."""
    occupation = get_person_occupation(person)
    if not occupation:
        return None

    category = categorize_occupation(occupation)
    birth_year = get_birth_year(person)

    # Профессия отца
    father_occupation = None
    father_category = None

    if person.child_family_id:
        family = data.families.get(person.child_family_id)
        if family and family.husband_id:
            father = data.get_person(family.husband_id)
            if father:
                father_occupation = get_person_occupation(father)
                if father_occupation:
                    father_category = categorize_occupation(father_occupation)

    return PersonOccupation(
        person=person,
        occupation=occupation,
        category=category,
        year=birth_year,
        father_occupation=father_occupation,
        father_category=father_category
    )


def analyze_all_occupations(data: GedcomData, before_year: Optional[int] = None) -> Dict:
    """Анализ всех профессий."""
    stats = {
        'total': 0,
        'with_occupation': 0,
        'cases': [],
        'by_category': defaultdict(list),
        'by_decade': defaultdict(lambda: defaultdict(int)),
        'social_mobility': {
            'same': 0,  # та же категория
            'up': 0,    # повышение
            'down': 0,  # понижение
            'lateral': 0,  # горизонтальное
            'pairs': []
        },
        'occupation_counts': defaultdict(int),
        'hereditary': defaultdict(int),  # наследование профессий
    }

    # Иерархия сословий для определения мобильности
    hierarchy = {
        'дворянство': 7,
        'духовенство': 6,
        'купечество': 5,
        'интеллигенция': 4,
        'чиновники': 4,
        'военные': 4,
        'мещанство': 3,
        'рабочие': 2,
        'крестьянство': 1,
        'обслуживание': 1,
        'другое': 0
    }

    for person_id, person in data.persons.items():
        stats['total'] += 1

        po = analyze_occupation(person, data)
        if not po:
            continue

        # Фильтр по году
        if before_year and po.year and po.year > before_year:
            continue

        stats['with_occupation'] += 1
        stats['cases'].append(po)
        stats['by_category'][po.category].append(po)
        stats['occupation_counts'][normalize_occupation(po.occupation)] += 1

        # По десятилетиям
        if po.year:
            decade = (po.year // 10) * 10
            stats['by_decade'][decade][po.category] += 1

        # Социальная мобильность (сравнение с отцом)
        if po.father_category and po.category:
            if po.category == po.father_category:
                stats['social_mobility']['same'] += 1
            else:
                child_level = hierarchy.get(po.category, 0)
                father_level = hierarchy.get(po.father_category, 0)

                if child_level > father_level:
                    stats['social_mobility']['up'] += 1
                    stats['social_mobility']['pairs'].append(('up', po))
                elif child_level < father_level:
                    stats['social_mobility']['down'] += 1
                    stats['social_mobility']['pairs'].append(('down', po))
                else:
                    stats['social_mobility']['lateral'] += 1

        # Наследование точной профессии
        if po.father_occupation:
            father_norm = normalize_occupation(po.father_occupation)
            child_norm = normalize_occupation(po.occupation)
            if father_norm == child_norm:
                stats['hereditary'][father_norm] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Анализ профессий и социальной мобильности'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--before', type=int, metavar='YEAR',
                        help='Анализировать только персон, рождённых до указанного года')
    parser.add_argument('--by-period', action='store_true',
                        help='Показать распределение по периодам')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ПРОФЕССИЙ И СОСЛОВИЙ")
    if args.before:
        output_lines.append(f"(рождённые до {args.before} года)")
    output_lines.append("=" * 100)

    stats = analyze_all_occupations(data, args.before)

    # Общая статистика
    output_lines.append(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    output_lines.append(f"   Всего персон: {stats['total']}")
    output_lines.append(f"   С известной профессией/сословием: {stats['with_occupation']}")

    if stats['total'] > 0:
        pct = stats['with_occupation'] / stats['total'] * 100
        output_lines.append(f"   Процент: {pct:.1f}%")

    # По категориям
    if stats['by_category']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👥 РАСПРЕДЕЛЕНИЕ ПО СОСЛОВИЯМ/КАТЕГОРИЯМ")
        output_lines.append("=" * 100)

        sorted_cats = sorted(stats['by_category'].items(),
                           key=lambda x: -len(x[1]))
        total_with_cat = stats['with_occupation']

        for category, persons in sorted_cats:
            count = len(persons)
            pct = count / total_with_cat * 100 if total_with_cat > 0 else 0
            output_lines.append(f"\n   {category.upper()} ({count}, {pct:.1f}%):")

            # Топ профессий в категории
            prof_counts = defaultdict(int)
            for po in persons:
                prof_counts[po.occupation] += 1

            top_profs = sorted(prof_counts.items(), key=lambda x: -x[1])[:5]
            for prof, cnt in top_profs:
                output_lines.append(f"      • {prof}: {cnt}")

    # Топ профессий
    if stats['occupation_counts']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🔝 САМЫЕ ЧАСТЫЕ ПРОФЕССИИ")
        output_lines.append("=" * 100)

        top = sorted(stats['occupation_counts'].items(), key=lambda x: -x[1])[:20]
        for occ, count in top:
            output_lines.append(f"   {occ}: {count}")

    # Социальная мобильность
    mobility = stats['social_mobility']
    total_mobility = mobility['same'] + mobility['up'] + mobility['down'] + mobility['lateral']

    if total_mobility > 0:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📈 СОЦИАЛЬНАЯ МОБИЛЬНОСТЬ")
        output_lines.append("=" * 100)

        output_lines.append(f"\n   Сравнение сословия/категории с отцом:")
        output_lines.append(f"   Всего пар отец-ребёнок с известными профессиями: {total_mobility}")

        same_pct = mobility['same'] / total_mobility * 100
        up_pct = mobility['up'] / total_mobility * 100
        down_pct = mobility['down'] / total_mobility * 100
        lateral_pct = mobility['lateral'] / total_mobility * 100

        output_lines.append(f"\n   Та же категория: {mobility['same']} ({same_pct:.1f}%)")
        output_lines.append(f"   Повышение: {mobility['up']} ({up_pct:.1f}%)")
        output_lines.append(f"   Понижение: {mobility['down']} ({down_pct:.1f}%)")
        output_lines.append(f"   Горизонтальное: {mobility['lateral']} ({lateral_pct:.1f}%)")

        # Примеры повышения
        up_cases = [p for t, p in mobility['pairs'] if t == 'up']
        if up_cases:
            output_lines.append(f"\n   📈 Примеры социального повышения:")
            for po in up_cases[:5]:
                output_lines.append(f"      {po.person.name}: {po.father_category} → {po.category}")
                output_lines.append(f"         ({po.father_occupation} → {po.occupation})")

        # Примеры понижения
        down_cases = [p for t, p in mobility['pairs'] if t == 'down']
        if down_cases:
            output_lines.append(f"\n   📉 Примеры социального понижения:")
            for po in down_cases[:5]:
                output_lines.append(f"      {po.person.name}: {po.father_category} → {po.category}")
                output_lines.append(f"         ({po.father_occupation} → {po.occupation})")

    # Наследование профессий
    if stats['hereditary']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("👨‍👦 НАСЛЕДОВАНИЕ ПРОФЕССИЙ")
        output_lines.append("=" * 100)

        output_lines.append("\n   Профессии, передающиеся от отца к сыну:")
        sorted_hereditary = sorted(stats['hereditary'].items(), key=lambda x: -x[1])
        for prof, count in sorted_hereditary[:10]:
            if count > 1:
                output_lines.append(f"      {prof}: {count} случаев")

    # По периодам
    if args.by_period and stats['by_decade']:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📅 РАСПРЕДЕЛЕНИЕ ПО ДЕСЯТИЛЕТИЯМ")
        output_lines.append("=" * 100)

        for decade in sorted(stats['by_decade'].keys()):
            cats = stats['by_decade'][decade]
            total = sum(cats.values())
            output_lines.append(f"\n   {decade}s ({total} персон):")

            sorted_cats = sorted(cats.items(), key=lambda x: -x[1])
            for cat, count in sorted_cats[:5]:
                pct = count / total * 100 if total > 0 else 0
                output_lines.append(f"      {cat}: {count} ({pct:.1f}%)")

    # Интерпретация
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 ИНТЕРПРЕТАЦИЯ")
    output_lines.append("=" * 100)
    output_lines.append("""
   Сословная система России (до 1917):

   • Дворянство — высшее сословие, землевладельцы
   • Духовенство — служители церкви, часто наследственное
   • Купечество — торговцы по гильдиям (1-я богатейшая)
   • Мещанство — городское среднее сословие
   • Крестьянство — основная масса населения

   Социальная мобильность:
   • Наследование профессий — типично для духовенства, ремесленников
   • Повышение через образование, военную службу, богатство
   • После 1861 (отмена крепостного права) — рост мобильности
   • После 1917 — разрушение сословной системы

   ⚠️ Профессии в GEDCOM могут быть неполными.
   Добавьте поле OCCU для каждой персоны.
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
