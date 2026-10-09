"""Held-out TEP wordings for generator profile v3 (RU/KZ).

Labels, unit spellings and sentence templates that the extractor's lexicon
(`src/ner/data/tep_lexicon.json`) does not contain. `dev` is for tuning the
extractor, `test` only for the final numbers; extractor code must never import
this module (tests/test_heldout.py). Written by the author of the extractor:
leakage is reduced (separate halves, committed before the extractor), not ruled out.
"""

HELDOUT = {
    "ru": {
        "dev": {
            "labels": {
                "floors": ("Число этажей", "Кол-во этажей надземной части", "Этажей, шт."),
                "building_area_m2": ("Пл. застройки", "Площадь, занятая зданием", "Застроенная площадь"),
                "total_area_m2": ("Общ. площадь здания", "Площадь здания общая", "Суммарная площадь помещений"),
                "construction_volume_m3": ("Объём строит. здания", "Строит. объём",
                                           "Объём строительный здания"),
                "underground_volume_m3": ("в т. ч. подземной части", "в том числе подземная часть здания"),
                "estimated_cost_ktg": ("Стоимость строительства по смете (с НДС)", "Сметная ст-ть, всего"),
                "construction_duration_months": ("Срок строительства",
                                                 "Нормативная продолжительность строительства"),
            },
            "units": {"m2": ("кв. м", "м кв."), "m3": ("куб. м", "м куб."), "floor": ("эт",),
                      "kKZT": ("тыс. тг",), "month": ("месяцев",)},
            "templates": {
                "eng_construction_volume_m3": ("Строительный объём {gen} принят {v} м³.",
                                               "Объём {gen} (строительный) равняется {v} куб. м."),
                "eng_total_area_m2": ("Площадь {gen} общая — {v} м².", "Общая пл. {gen} составит {v} кв. м."),
                "object_axes": ("{name}: этажей — {floors}, размеры в осях {a} × {b} м.",),
            },
        },
        "test": {
            "labels": {
                "floors": ("Кол. этажей", "Количество надземных этажей", "Число надземных этажей"),
                "building_area_m2": ("Площадь под застройку", "Пл. застр. здания", "Площадь, занимаемая зданием"),
                "total_area_m2": ("Общ. пл. здания", "Общая пл. помещений", "Площадь здания, всего"),
                "construction_volume_m3": ("Объём здания (строительный)", "Стр. объём", "Объём строения"),
                "underground_volume_m3": ("в т. ч. подземная часть", "из них подземная часть"),
                "estimated_cost_ktg": ("Стоимость строительства (с НДС), всего", "Сметная ст-ть строительства"),
                "construction_duration_months": ("Срок строительства, всего", "Продолж. строительства"),
            },
            "units": {"m2": ("м.кв.", "кв.м."), "m3": ("м.куб.", "куб.м."), "floor": ("этажей",),
                      "kKZT": ("тыс.тенге",), "month": ("мес",)},
            "templates": {
                "eng_construction_volume_m3": ("Объём строительный {gen}: {v} куб. м.",
                                               "Для {gen} строительный объём равен {v} м³."),
                "eng_total_area_m2": ("Общая площадь помещений {gen}: {v} кв. м.",
                                      "Для {gen} принята общая площадь {v} м²."),
                "object_axes": ("{name}: количество этажей — {floors}, размеры в осях {a} × {b} м.",),
            },
        },
    },
    "kz": {
        "dev": {
            "labels": {
                "floors": ("Қабаттар саны", "Жер үсті қабаттарының саны"),
                "building_area_m2": ("Салынған аудан", "Ғимарат алып жатқан аудан"),
                "total_area_m2": ("Ғимараттың жалпы алаңы", "Жалпы алаң"),
                "construction_volume_m3": ("Ғимарат көлемі (құрылыс)", "Құр. көлемі"),
                "underground_volume_m3": ("жерасты бөлігі қоса алғанда",),
                "estimated_cost_ktg": ("Құрылыстың сметалық бағасы (ҚҚС-пен)", "Сметалық құн, барлығы"),
                "construction_duration_months": ("Құрылыс мерзімі",),
            },
            "units": {"m2": ("кв. м",), "m3": ("куб. м",), "floor": ("қаб.",), "kKZT": ("мың тг",),
                      "month": ("айлар",)},
            "templates": {
                "eng_construction_volume_m3": ("{gen_cap} құрылыс көлемі {v} м³ болып қабылданды.",
                                               "{gen_cap} көлемі (құрылыс) {v} куб. м тең."),
                "eng_total_area_m2": ("{gen_cap} жалпы алаңы — {v} м².", "{gen_cap} {v} м² жалпы алаңы қабылданды."),
                "object_axes": ("{name}: қабат саны — {floors}, осьтер бойынша өлшемдері {a} × {b} м.",),
            },
        },
        "test": {
            "labels": {
                "floors": ("Қабаттар саны (жер үсті)", "Қабаттылық"),
                "building_area_m2": ("Салынған алаң", "Ғимарат астындағы аудан"),
                "total_area_m2": ("Жалпы алаңы", "Ғимарат ауданы (жалпы)"),
                "construction_volume_m3": ("Құрылыстық көлем", "Ғимараттың көлемі, құрылыс"),
                "underground_volume_m3": ("жер асты бөлігі",),
                "estimated_cost_ktg": ("Сметалық құны (ҚҚС қоса)",),
                "construction_duration_months": ("Құрылыс мерзімі, барлығы", "Салу ұзақтығы"),
            },
            "units": {"m2": ("ш. м.",), "m3": ("т. м.",), "floor": ("қабаттар",), "kKZT": ("мың. теңге",),
                      "month": ("ай.",)},
            "templates": {
                "eng_construction_volume_m3": ("{gen_cap} құрылыстық көлемі {v} куб. м құрайды.",
                                               "{gen_cap} {v} м³ құрылыстық көлемі есептелген."),
                "eng_total_area_m2": ("{gen_cap} жалпы алаңы {v} кв. м құрайды.",
                                      "{gen_cap} {v} м² жалпы алаң есептелген."),
                "object_axes": ("{name} — {floors} қабатты ғимарат, осьтерде {a} × {b} м.",),
            },
        },
    },
}
