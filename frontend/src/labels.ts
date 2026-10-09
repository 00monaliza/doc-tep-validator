import type { Section, Verdict } from "./types";

export const SECTIONS: Section[] = ["PZ", "AR", "KR", "SMETA"];
export const SECTION: Record<Section, string> = { PZ: "ПЗ", AR: "АР", KR: "КР", SMETA: "Смета" };
export const SECTION_FULL: Record<Section, string> = {
  PZ: "Пояснительная записка", AR: "Архитектурные решения",
  KR: "Конструктивные решения", SMETA: "Сметная документация",
};
export const VERDICT: Record<Verdict, string> = { MISMATCH: "Расхождение", MISSING: "Нет значения", MATCH: "Совпадает" };

const FIELD: Record<string, string> = {
  floors: "Этажность", building_area_m2: "Площадь застройки, м²", total_area_m2: "Общая площадь, м²",
  construction_volume_m3: "Строительный объём, м³", underground_volume_m3: "в т. ч. подземной части, м³",
  estimated_cost_ktg: "Сметная стоимость, тыс. тенге", construction_duration_months: "Продолжительность, мес.",
  explication_total_area_m2: "Итого по экспликации, м²", concrete_total_m3: "Расход бетона всего, м³",
  concrete_b25_foundation_m3: "Бетон B25, м³", concrete_b30_frame_m3: "Бетон B30, м³", rebar_a500c_t: "Арматура A500С, т",
  brick_masonry_m3: "Кирпичная кладка, м³", steel_structures_t: "Стальные конструкции, т",
  "os.total_ktg": "Итого по объектной смете, тыс. тенге", "ssr.total_ktg": "Всего по ССР, тыс. тенге",
  "local.total_tg": "Всего по локальной смете, тенге", useful_area_m2: "Полезная площадь, м²",
  seismicity_points: "Сейсмичность, баллов", fire_resistance: "Степень огнестойкости",
};

export function fieldName(f: string): string {
  if (FIELD[f]) return FIELD[f];
  const local = FIELD[f.replace("local_qty.", "")];
  if (f.startsWith("local_qty.") && local) return `ЛС: ${local}`;
  if (f.startsWith("ssr.ch2.os_")) return `Строка ОС ${f.slice(11, 16)} в ССР, тыс. тенге`;
  if (f.startsWith("col:")) return f.slice(4);
  return f;
}

export const TYPE: Record<string, string> = {
  AREA_PZ_VS_AR_EXPLICATION: "ПЗ ↔ экспликация АР", MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE: "КР ↔ локальная смета",
  COST_OBJECT_ESTIMATE_VS_SUMMARY: "Объектная смета ↔ ССР", MISSING_MANDATORY_TEP: "Обязательный ТЭП",
  TABLE_TOTAL_MISMATCH: "Итог таблицы", TEP_CROSS_SECTION_MISMATCH: "Один ТЭП в разных местах ПЗ",
  PARAMETER_CONTRADICTION: "Противоречие параметров", GEOMETRY_INCONSISTENCY: "Геометрия",
};

export const LANG: Record<string, string> = { ru: "русский", kz: "казахский", mixed: "смешанный" };

export const fmt = (v: unknown): string =>
  v == null ? "—" : typeof v === "string" ? v : Number(v).toLocaleString("ru-RU", { maximumFractionDigits: 3 });
