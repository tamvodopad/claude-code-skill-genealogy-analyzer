#!/usr/bin/env python3
"""
Расчёт коэффициента инбридинга (COI) по алгоритму Райта.
Находит общих предков и рассчитывает степень родства супругов.

Использование:
    python3 inbreeding.py tree.ged
    python3 inbreeding.py tree.ged --person @I1@  # для конкретной персоны
    python3 inbreeding.py tree.ged --max-gen 10   # глубина поиска
"""

import sys
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Set, Tuple
from collections import defaultdict

sys.path.insert(0, '.')
from lib import parse_gedcom, Person, Family, GedcomData


@dataclass
class CommonAncestor:
    """Общий предок."""
    ancestor: Person
    path_from_father: int  # поколений от отца до предка
    path_from_mother: int  # поколений от матери до предка
    contribution: float    # вклад в COI


@dataclass
class InbreedingResult:
    """Результат расчёта инбридинга."""
    person: Person
    coi: float  # Coefficient of Inbreeding (0-1)
    coi_percent: float
    common_ancestors: List[CommonAncestor]
    parents_related: bool
    relationship_description: str


def find_ancestors_with_paths(person: Person, data: GedcomData,
                               max_generations: int = 10) -> Dict[str, List[int]]:
    """
    Находит всех предков персоны с путями (количество поколений).
    Возвращает {ancestor_id: [список путей до этого предка]}.
    """
    ancestors = defaultdict(list)

    def traverse(current: Person, generation: int, visited: Set[str]):
        if generation > max_generations:
            return
        if current.id in visited:
            return

        visited.add(current.id)

        father, mother = data.get_parents(current)

        if father:
            ancestors[father.id].append(generation + 1)
            traverse(father, generation + 1, visited.copy())

        if mother:
            ancestors[mother.id].append(generation + 1)
            traverse(mother, generation + 1, visited.copy())

    traverse(person, 0, set())
    return dict(ancestors)


def find_ancestors_recursive(person: Person, data: GedcomData,
                              generation: int, max_gen: int,
                              path: List[str]) -> List[Tuple[str, int, List[str]]]:
    """
    Рекурсивный поиск предков с сохранением полного пути.
    Возвращает [(ancestor_id, generation, path), ...]
    """
    if generation > max_gen:
        return []

    results = []
    father, mother = data.get_parents(person)

    if father:
        new_path = path + [father.id]
        results.append((father.id, generation + 1, new_path))
        results.extend(find_ancestors_recursive(father, data, generation + 1, max_gen, new_path))

    if mother:
        new_path = path + [mother.id]
        results.append((mother.id, generation + 1, new_path))
        results.extend(find_ancestors_recursive(mother, data, generation + 1, max_gen, new_path))

    return results


def calculate_coi(person: Person, data: GedcomData,
                  max_generations: int = 10) -> InbreedingResult:
    """
    Расчёт коэффициента инбридинга по формуле Райта.

    COI = Σ (0.5)^(n1 + n2 + 1) * (1 + Fa)

    где:
    - n1 = поколений от отца до общего предка
    - n2 = поколений от матери до общего предка
    - Fa = COI общего предка (упрощённо = 0)
    """
    father, mother = data.get_parents(person)

    if not father or not mother:
        return InbreedingResult(
            person=person,
            coi=0.0,
            coi_percent=0.0,
            common_ancestors=[],
            parents_related=False,
            relationship_description="Нет данных о родителях"
        )

    # Находим предков отца и матери
    father_ancestors = find_ancestors_recursive(father, data, 0, max_generations, [father.id])
    mother_ancestors = find_ancestors_recursive(mother, data, 0, max_generations, [mother.id])

    # Группируем по ID предка
    father_paths = defaultdict(list)
    for anc_id, gen, path in father_ancestors:
        father_paths[anc_id].append((gen, path))

    mother_paths = defaultdict(list)
    for anc_id, gen, path in mother_ancestors:
        mother_paths[anc_id].append((gen, path))

    # Находим общих предков
    common_ancestor_ids = set(father_paths.keys()) & set(mother_paths.keys())

    if not common_ancestor_ids:
        return InbreedingResult(
            person=person,
            coi=0.0,
            coi_percent=0.0,
            common_ancestors=[],
            parents_related=False,
            relationship_description="Общие предки не найдены (в пределах {max_generations} поколений)"
        )

    # Рассчитываем COI
    coi = 0.0
    common_ancestors = []

    for anc_id in common_ancestor_ids:
        ancestor = data.get_person(anc_id)
        if not ancestor:
            continue

        # Для каждой комбинации путей
        for f_gen, f_path in father_paths[anc_id]:
            for m_gen, m_path in mother_paths[anc_id]:
                # Проверяем, что пути не пересекаются (кроме самого предка)
                f_set = set(f_path[:-1])  # без общего предка
                m_set = set(m_path[:-1])

                if f_set & m_set:
                    continue  # Пути пересекаются - не считаем

                # Вклад этого предка: (0.5)^(n1 + n2 + 1)
                contribution = (0.5) ** (f_gen + m_gen + 1)
                coi += contribution

                common_ancestors.append(CommonAncestor(
                    ancestor=ancestor,
                    path_from_father=f_gen,
                    path_from_mother=m_gen,
                    contribution=contribution
                ))

    # Убираем дубликаты предков, оставляя ближайший путь
    unique_ancestors = {}
    for ca in common_ancestors:
        key = ca.ancestor.id
        if key not in unique_ancestors or ca.contribution > unique_ancestors[key].contribution:
            unique_ancestors[key] = ca

    common_ancestors = sorted(unique_ancestors.values(),
                               key=lambda x: -x.contribution)

    # Описание родства
    relationship = describe_relationship(common_ancestors, data)

    return InbreedingResult(
        person=person,
        coi=coi,
        coi_percent=coi * 100,
        common_ancestors=common_ancestors,
        parents_related=True,
        relationship_description=relationship
    )


def describe_relationship(common_ancestors: List[CommonAncestor], data: GedcomData) -> str:
    """Описание степени родства."""
    if not common_ancestors:
        return "Родство не обнаружено"

    closest = common_ancestors[0]
    n1 = closest.path_from_father
    n2 = closest.path_from_mother

    # Типичные отношения
    relationships = {
        (1, 1): "Родители — родные брат и сестра",
        (1, 2): "Отец — дядя/тётя матери",
        (2, 1): "Мать — дядя/тётя отца",
        (2, 2): "Родители — двоюродные брат и сестра",
        (2, 3): "Родители — троюродные брат и сестра (через поколение)",
        (3, 2): "Родители — троюродные брат и сестра (через поколение)",
        (3, 3): "Родители — троюродные брат и сестра",
        (4, 4): "Родители — четвероюродные брат и сестра",
    }

    key = (min(n1, n2), max(n1, n2))
    if key in relationships:
        return relationships[key]

    # Общее описание
    total_gen = n1 + n2
    if total_gen <= 4:
        return f"Близкое родство ({total_gen} поколения до общего предка)"
    elif total_gen <= 6:
        return f"Среднее родство ({total_gen} поколений до общего предка)"
    else:
        return f"Дальнее родство ({total_gen} поколений до общего предка)"


def analyze_all_persons(data: GedcomData, max_generations: int = 10,
                         min_coi: float = 0.0) -> List[InbreedingResult]:
    """Анализ инбридинга для всех персон."""
    results = []

    for person_id, person in data.persons.items():
        result = calculate_coi(person, data, max_generations)
        if result.coi >= min_coi:
            results.append(result)

    return sorted(results, key=lambda x: -x.coi)


def find_related_marriages(data: GedcomData, max_generations: int = 10) -> List[Tuple[Family, InbreedingResult]]:
    """Находит браки между родственниками."""
    related_marriages = []

    for family_id, family in data.families.items():
        if not family.husband_id or not family.wife_id:
            continue

        husband = data.get_person(family.husband_id)
        wife = data.get_person(family.wife_id)

        if not husband or not wife:
            continue

        # Находим общих предков супругов
        husband_ancestors = set()
        for anc_id, gen, path in find_ancestors_recursive(husband, data, 0, max_generations, [husband.id]):
            husband_ancestors.add(anc_id)

        wife_ancestors = set()
        for anc_id, gen, path in find_ancestors_recursive(wife, data, 0, max_generations, [wife.id]):
            wife_ancestors.add(anc_id)

        common = husband_ancestors & wife_ancestors

        if common:
            # Берём первого ребёнка для расчёта COI
            if family.children_ids:
                child = data.get_person(family.children_ids[0])
                if child:
                    result = calculate_coi(child, data, max_generations)
                    if result.coi > 0:
                        related_marriages.append((family, result))

    return sorted(related_marriages, key=lambda x: -x[1].coi)


def main():
    parser = argparse.ArgumentParser(
        description='Расчёт коэффициента инбридинга (COI) по алгоритму Райта'
    )
    parser.add_argument('gedcom_file', help='Путь к GEDCOM файлу')
    parser.add_argument('--person', metavar='ID',
                        help='ID персоны для анализа (например, @I1@)')
    parser.add_argument('--max-gen', type=int, default=10, metavar='N',
                        help='Максимальная глубина поиска предков (по умолчанию: 10)')
    parser.add_argument('--min-coi', type=float, default=0.001, metavar='X',
                        help='Минимальный COI для отображения (по умолчанию: 0.001 = 0.1%%)')
    parser.add_argument('--output', '-o', metavar='FILE',
                        help='Сохранить отчёт в файл')

    args = parser.parse_args()

    print(f"Парсинг GEDCOM файла: {args.gedcom_file}")
    data = parse_gedcom(args.gedcom_file)
    print(f"Загружено: {len(data.persons)} персон, {len(data.families)} семей\n")

    output_lines = []

    output_lines.append("=" * 100)
    output_lines.append("АНАЛИЗ ИНБРИДИНГА (КОЭФФИЦИЕНТ РАЙТА)")
    output_lines.append("=" * 100)

    if args.person:
        # Анализ конкретной персоны
        person = data.get_person(args.person)
        if not person:
            print(f"Ошибка: персона {args.person} не найдена")
            sys.exit(1)

        result = calculate_coi(person, data, args.max_gen)

        output_lines.append(f"\n📊 АНАЛИЗ ДЛЯ: {person.name}")
        output_lines.append(f"   Коэффициент инбридинга (COI): {result.coi_percent:.4f}%")

        if result.coi > 0:
            output_lines.append(f"\n   {result.relationship_description}")
            output_lines.append(f"\n   📌 Общие предки родителей:")
            for ca in result.common_ancestors[:10]:
                output_lines.append(f"      • {ca.ancestor.name}")
                output_lines.append(f"        От отца: {ca.path_from_father} поколений, от матери: {ca.path_from_mother} поколений")
                output_lines.append(f"        Вклад в COI: {ca.contribution * 100:.4f}%")
        else:
            output_lines.append(f"\n   ✓ Родители не являются родственниками (в пределах {args.max_gen} поколений)")

    else:
        # Анализ всех
        output_lines.append(f"\n🔍 Поиск браков между родственниками (до {args.max_gen} поколений)...")

        related = find_related_marriages(data, args.max_gen)

        if not related:
            output_lines.append("\n✓ Браки между родственниками не обнаружены")
        else:
            output_lines.append(f"\n⚠️ Найдено {len(related)} браков между родственниками:")

            # Группируем по уровню COI
            high_coi = [(f, r) for f, r in related if r.coi >= 0.0625]    # >= 6.25%
            medium_coi = [(f, r) for f, r in related if 0.01 <= r.coi < 0.0625]  # 1-6.25%
            low_coi = [(f, r) for f, r in related if r.coi < 0.01]  # < 1%

            if high_coi:
                output_lines.append("\n" + "=" * 100)
                output_lines.append("🔴 ВЫСОКИЙ ИНБРИДИНГ (COI ≥ 6.25%)")
                output_lines.append("=" * 100)

                for family, result in high_coi:
                    husband = data.get_person(family.husband_id)
                    wife = data.get_person(family.wife_id)
                    output_lines.append(f"\n   👫 {husband.name if husband else '?'} + {wife.name if wife else '?'}")
                    output_lines.append(f"      COI детей: {result.coi_percent:.2f}%")
                    output_lines.append(f"      {result.relationship_description}")
                    if result.common_ancestors:
                        output_lines.append(f"      Ближайший общий предок: {result.common_ancestors[0].ancestor.name}")

            if medium_coi:
                output_lines.append("\n" + "=" * 100)
                output_lines.append("🟡 СРЕДНИЙ ИНБРИДИНГ (1% ≤ COI < 6.25%)")
                output_lines.append("=" * 100)

                for family, result in medium_coi[:20]:
                    husband = data.get_person(family.husband_id)
                    wife = data.get_person(family.wife_id)
                    output_lines.append(f"\n   👫 {husband.name if husband else '?'} + {wife.name if wife else '?'}")
                    output_lines.append(f"      COI: {result.coi_percent:.2f}% — {result.relationship_description}")

                if len(medium_coi) > 20:
                    output_lines.append(f"\n   ... и ещё {len(medium_coi) - 20}")

            if low_coi:
                output_lines.append("\n" + "=" * 100)
                output_lines.append("🟢 НИЗКИЙ ИНБРИДИНГ (COI < 1%)")
                output_lines.append("=" * 100)
                output_lines.append(f"\n   Найдено {len(low_coi)} браков с дальним родством")

                for family, result in low_coi[:10]:
                    husband = data.get_person(family.husband_id)
                    wife = data.get_person(family.wife_id)
                    output_lines.append(f"   • {husband.name if husband else '?'} + {wife.name if wife else '?'} — COI: {result.coi_percent:.3f}%")

        # Статистика
        output_lines.append("\n" + "=" * 100)
        output_lines.append("📈 СТАТИСТИКА")
        output_lines.append("=" * 100)
        output_lines.append(f"   Всего семей: {len(data.families)}")
        output_lines.append(f"   Браков между родственниками: {len(related)}")
        if related:
            avg_coi = sum(r.coi for _, r in related) / len(related)
            max_coi = max(r.coi for _, r in related)
            output_lines.append(f"   Средний COI: {avg_coi * 100:.3f}%")
            output_lines.append(f"   Максимальный COI: {max_coi * 100:.2f}%")

    # Справка
    output_lines.append("\n" + "=" * 100)
    output_lines.append("📖 СПРАВКА ПО COI")
    output_lines.append("=" * 100)
    output_lines.append("""
   COI (Coefficient of Inbreeding) — вероятность, что два аллеля
   в любом локусе идентичны по происхождению.

   Типичные значения:
   • 25%    — родители — родные брат и сестра
   • 12.5%  — родители — дядя/племянница
   • 6.25%  — родители — двоюродные брат и сестра
   • 1.56%  — родители — троюродные брат и сестра
   • 0.39%  — родители — четвероюродные брат и сестра

   В крестьянских общинах России браки троюродных и более дальних
   родственников были нормой из-за ограниченного населения деревень.
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
