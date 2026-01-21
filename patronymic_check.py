#!/usr/bin/env python3
"""
Проверка соответствия отчеств детей именам отцов.
Находит несоответствия, которые могут указывать на:
- Ошибки в данных
- Приёмных детей
- Внебрачных детей
- Нестандартное образование отчества

Использование:
    python3 patronymic_check.py tree.ged
    python3 patronymic_check.py tree.ged --before 1920
"""

import sys
import argparse
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, GedcomData


# Правила образования отчеств от русских имён
PATRONYMIC_RULES: Dict[str, Tuple[str, str]] = {
    # Имя: (мужское отчество, женское отчество)
    # Имена на -й
    "Андрей": ("Андреевич", "Андреевна"),
    "Алексей": ("Алексеевич", "Алексеевна"),
    "Сергей": ("Сергеевич", "Сергеевна"),
    "Николай": ("Николаевич", "Николаевна"),
    "Дмитрий": ("Дмитриевич", "Дмитриевна"),
    "Евгений": ("Евгеньевич", "Евгеньевна"),
    "Василий": ("Васильевич", "Васильевна"),
    "Григорий": ("Григорьевич", "Григорьевна"),
    "Юрий": ("Юрьевич", "Юрьевна"),
    "Виталий": ("Витальевич", "Витальевна"),
    "Анатолий": ("Анатольевич", "Анатольевна"),
    "Аркадий": ("Аркадьевич", "Аркадьевна"),
    "Валерий": ("Валерьевич", "Валерьевна"),
    "Геннадий": ("Геннадьевич", "Геннадьевна"),
    "Матвей": ("Матвеевич", "Матвеевна"),
    "Тимофей": ("Тимофеевич", "Тимофеевна"),

    # Имена на мягкий знак
    "Игорь": ("Игоревич", "Игоревна"),

    # Имена на гласную
    "Илья": ("Ильич", "Ильинична"),
    "Лука": ("Лукич", "Лукинична"),
    "Никита": ("Никитич", "Никитична"),
    "Фома": ("Фомич", "Фоминична"),
    "Кузьма": ("Кузьмич", "Кузьминична"),
    "Савва": ("Саввич", "Саввична"),

    # Стандартные имена на согласную
    "Иван": ("Иванович", "Ивановна"),
    "Пётр": ("Петрович", "Петровна"),
    "Петр": ("Петрович", "Петровна"),
    "Александр": ("Александрович", "Александровна"),
    "Михаил": ("Михайлович", "Михайловна"),
    "Павел": ("Павлович", "Павловна"),
    "Владимир": ("Владимирович", "Владимировна"),
    "Фёдор": ("Фёдорович", "Фёдоровна"),
    "Федор": ("Федорович", "Федоровна"),
    "Степан": ("Степанович", "Степановна"),
    "Константин": ("Константинович", "Константиновна"),
    "Семён": ("Семёнович", "Семёновна"),
    "Семен": ("Семенович", "Семеновна"),
    "Борис": ("Борисович", "Борисовна"),
    "Виктор": ("Викторович", "Викторовна"),
    "Яков": ("Яковлевич", "Яковлевна"),
    "Антон": ("Антонович", "Антоновна"),
    "Роман": ("Романович", "Романовна"),
    "Максим": ("Максимович", "Максимовна"),
    "Леонид": ("Леонидович", "Леонидовна"),
    "Олег": ("Олегович", "Олеговна"),
    "Егор": ("Егорович", "Егоровна"),
    "Даниил": ("Даниилович", "Данииловна"),
    "Данил": ("Данилович", "Даниловна"),
    "Артём": ("Артёмович", "Артёмовна"),
    "Артем": ("Артемович", "Артемовна"),
    "Кирилл": ("Кириллович", "Кирилловна"),
    "Денис": ("Денисович", "Денисовна"),
    "Никифор": ("Никифорович", "Никифоровна"),
    "Прокофий": ("Прокофьевич", "Прокофьевна"),
    "Прокопий": ("Прокопьевич", "Прокопьевна"),
    "Ефим": ("Ефимович", "Ефимовна"),
    "Афанасий": ("Афанасьевич", "Афанасьевна"),
    "Тихон": ("Тихонович", "Тихоновна"),
    "Филипп": ("Филиппович", "Филипповна"),
    "Филип": ("Филипович", "Филиповна"),
    "Трофим": ("Трофимович", "Трофимовна"),
    "Гавриил": ("Гаврилович", "Гавриловна"),
    "Гаврила": ("Гаврилович", "Гавриловна"),
    "Макар": ("Макарович", "Макаровна"),
    "Герасим": ("Герасимович", "Герасимовна"),
    "Лев": ("Львович", "Львовна"),
    "Глеб": ("Глебович", "Глебовна"),
    "Наум": ("Наумович", "Наумовна"),
    "Захар": ("Захарович", "Захаровна"),
    "Ермолай": ("Ермолаевич", "Ермолаевна"),
    "Кондрат": ("Кондратьевич", "Кондратьевна"),
    "Кондратий": ("Кондратьевич", "Кондратьевна"),
}


def normalize_name(name: str) -> str:
    """Нормализация имени: убираем пробелы, приводим к начальной заглавной."""
    return name.strip().capitalize() if name else ""


def generate_patronymic(father_name: str, child_sex: str) -> Optional[str]:
    """
    Генерация ожидаемого отчества по имени отца и полу ребёнка.
    """
    if not father_name:
        return None

    name = normalize_name(father_name)

    # Сначала проверяем словарь исключений
    if name in PATRONYMIC_RULES:
        male, female = PATRONYMIC_RULES[name]
        return male if child_sex == 'M' else female

    # Пытаемся сгенерировать по правилам
    suffix_male = "ович"
    suffix_female = "овна"

    # Имена на -ий, -ей, -ай -> -ьевич/-ьевна
    if name.endswith(('ий', 'ей', 'ай')):
        base = name[:-2] if name.endswith('ий') else name[:-2]
        suffix_male = "ьевич"
        suffix_female = "ьевна"
        return base + (suffix_male if child_sex == 'M' else suffix_female)

    # Имена на мягкий знак -> -евич/-евна
    if name.endswith('ь'):
        base = name[:-1]
        suffix_male = "евич"
        suffix_female = "евна"
        return base + (suffix_male if child_sex == 'M' else suffix_female)

    # Имена на -а, -я (Илья, Никита) -> -ич/-ична
    if name.endswith(('а', 'я')):
        base = name[:-1]
        suffix_male = "ич"
        suffix_female = "ична"
        return base + (suffix_male if child_sex == 'M' else suffix_female)

    # Стандартный случай: согласная + -ович/-овна
    return name + (suffix_male if child_sex == 'M' else suffix_female)


def normalize_patronymic(patronymic: str) -> str:
    """Нормализация отчества для сравнения."""
    if not patronymic:
        return ""
    # Приводим к нижнему регистру, убираем ё -> е
    p = patronymic.lower().strip()
    p = p.replace('ё', 'е')
    return p


def compare_patronymics(actual: str, expected: str) -> bool:
    """Сравнение отчеств с учётом вариаций."""
    if not actual or not expected:
        return False

    a = normalize_patronymic(actual)
    e = normalize_patronymic(expected)

    if a == e:
        return True

    # Учитываем вариации ё/е
    if a.replace('е', 'ё') == e or a == e.replace('е', 'ё'):
        return True

    # Учитываем опечатки в одну букву (простое сравнение)
    if len(a) == len(e):
        diff = sum(1 for i in range(len(a)) if a[i] != e[i])
        if diff == 1:
            return True  # Считаем допустимой опечаткой

    return False


@dataclass
class PatronymicMismatch:
    """Несоответствие отчества."""
    child: Person
    father: Person
    child_patronymic: str
    expected_patronymic: str
    severity: str  # critical, warning


def check_patronymics(data: GedcomData, before_year: Optional[int] = None) -> Tuple[List[PatronymicMismatch], Dict]:
    """
    Проверка соответствия отчеств детей именам отцов.
    """
    mismatches = []
    stats = {
        'total_checked': 0,
        'matched': 0,
        'mismatched': 0,
        'no_patronymic': 0,
        'no_father': 0,
        'no_father_name': 0,
    }

    for person_id, person in data.persons.items():
        # Фильтр по году
        if before_year:
            birth_year = person.birth_year
            if person.birth_date:
                birth_year = person.birth_date.year
            if birth_year and birth_year > before_year:
                continue

        # Нужно отчество
        if not person.patronymic:
            stats['no_patronymic'] += 1
            continue

        # Нужен отец
        father, _ = data.get_parents(person)
        if not father:
            stats['no_father'] += 1
            continue

        if not father.given_name:
            stats['no_father_name'] += 1
            continue

        stats['total_checked'] += 1

        # Генерируем ожидаемое отчество
        expected = generate_patronymic(father.given_name, person.sex)

        if not expected:
            continue

        if compare_patronymics(person.patronymic, expected):
            stats['matched'] += 1
        else:
            stats['mismatched'] += 1

            # Определяем серьёзность
            # Если отчество совсем не похоже на ожидаемое - critical
            # Если похоже (опечатка в 1-2 буквы) - warning
            actual_norm = normalize_patronymic(person.patronymic)
            expected_norm = normalize_patronymic(expected)

            # Проверяем, начинаются ли с одной буквы
            same_start = actual_norm[:3] == expected_norm[:3] if len(actual_norm) >= 3 and len(expected_norm) >= 3 else False

            severity = "warning" if same_start else "critical"

            mismatches.append(PatronymicMismatch(
                child=person,
                father=father,
                child_patronymic=person.patronymic,
                expected_patronymic=expected,
                severity=severity
            ))

    return mismatches, stats


def main():
    parser = argparse.ArgumentParser(
        description='Проверка соответствия отчеств детей именам отцов'
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

    mismatches, stats = check_patronymics(data, args.before)

    # Формируем отчёт
    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("ПРОВЕРКА СООТВЕТСТВИЯ ОТЧЕСТВ ИМЕНАМ ОТЦОВ")
    if args.before:
        output_lines.append(f"(только записи до {args.before} года)")
    output_lines.append("=" * 100)

    output_lines.append(f"\n📊 СТАТИСТИКА:")
    output_lines.append(f"  ├─ Проверено записей: {stats['total_checked']}")
    output_lines.append(f"  ├─ Отчества совпадают: {stats['matched']} ✓")
    output_lines.append(f"  ├─ Несоответствия: {stats['mismatched']} ✗")
    output_lines.append(f"  ├─ Без отчества: {stats['no_patronymic']}")
    output_lines.append(f"  ├─ Без указанного отца: {stats['no_father']}")
    output_lines.append(f"  └─ Отец без имени: {stats['no_father_name']}")

    if stats['total_checked'] > 0:
        match_pct = 100 * stats['matched'] / stats['total_checked']
        output_lines.append(f"\n  📈 Точность отчеств: {match_pct:.1f}%")

    # Критические несоответствия
    critical = [m for m in mismatches if m.severity == 'critical']
    warnings = [m for m in mismatches if m.severity == 'warning']

    if critical:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🔴 КРИТИЧЕСКИЕ НЕСООТВЕТСТВИЯ")
        output_lines.append("(Отчество сильно отличается от ожидаемого — возможна ошибка в данных)")
        output_lines.append("=" * 100)

        for m in critical:
            child_birth = m.child.birth_year or (m.child.birth_date.year if m.child.birth_date else "?")
            output_lines.append(f"\n• {m.child.name} ({child_birth})")
            output_lines.append(f"  Отчество: {m.child_patronymic}")
            output_lines.append(f"  Ожидалось: {m.expected_patronymic}")
            output_lines.append(f"  Отец: {m.father.name} (имя: {m.father.given_name})")

    if warnings:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("🟡 ПРЕДУПРЕЖДЕНИЯ")
        output_lines.append("(Небольшие расхождения — возможны опечатки или нестандартное образование)")
        output_lines.append("=" * 100)

        for m in warnings[:30]:  # Ограничиваем вывод
            child_birth = m.child.birth_year or (m.child.birth_date.year if m.child.birth_date else "?")
            output_lines.append(f"\n• {m.child.name} ({child_birth})")
            output_lines.append(f"  Отчество: {m.child_patronymic}")
            output_lines.append(f"  Ожидалось: {m.expected_patronymic}")
            output_lines.append(f"  Отец: {m.father.name}")

        if len(warnings) > 30:
            output_lines.append(f"\n... и ещё {len(warnings) - 30} предупреждений")

    # Анализ паттернов
    if mismatches:
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📈 АНАЛИЗ НЕСООТВЕТСТВИЙ")
        output_lines.append("=" * 100)

        # Группируем по отцам
        by_father = defaultdict(list)
        for m in mismatches:
            by_father[m.father.id].append(m)

        fathers_with_multiple = [(fid, ms) for fid, ms in by_father.items() if len(ms) > 1]
        if fathers_with_multiple:
            output_lines.append(f"\n🔍 Отцы с несколькими детьми с несовпадающими отчествами:")
            for fid, ms in sorted(fathers_with_multiple, key=lambda x: -len(x[1]))[:10]:
                father = data.get_person(fid)
                output_lines.append(f"  • {father.name} — {len(ms)} детей с несовпадениями")

    # Вывод
    report = "\n".join(output_lines)
    print(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n💾 Отчёт сохранён в: {args.output}")


if __name__ == '__main__':
    main()
