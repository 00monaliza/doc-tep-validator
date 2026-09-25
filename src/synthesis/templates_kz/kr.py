"""Конструктивтік шешімдер — мәтіндік бөлігі және материалдар ведомосы (KZ)."""

from src.ner.common.taxonomy import MATERIALS, Section
from src.synthesis.context import Ctx
from src.synthesis.data import kz_lexicon as lex
from src.synthesis.document import Document, TableRows

S = Section.KR


def build(ctx: Ctx) -> Document:
    m, v = ctx.meta, ctx.v
    doc = Document(S.value, "kz", f"{m.project_code}-КШ", "4-бөлім. Конструктивтік шешімдер. Мәтіндік бөлігі")
    doc.title_block(f"«{m.object_name}»")

    doc.heading("1. Конструктивтік сұлба")
    doc.para(ctx.pick(
        "Ғимараттың конструктивтік сұлбасы — қаңқалы, монолитті темірбетон бағаналар мен аражабын "
        "тақталарынан тұрады. Кеңістіктік қаттылықты бағаналардың, диафрагмалардың және аражабын "
        "дискілерінің бірлескен жұмысы қамтамасыз етеді.",
        "Ғимарат бағаналар мен аражабын тақталарының түйіндері қатаң түйіскен монолитті темірбетон "
        "қаңқамен жобаланған.",
    ))
    doc.para(f"Іргетастар — B25, W6, F150 сыныпты бетоннан жасалған қалыңдығы {v.foundation_thickness_mm} мм "
             f"монолитті темірбетон тақта. Сыртқы қабырғалар — керамикалық кірпіштен қалау.")

    doc.heading("2. Негізгі конструктивтік материалдар көлемдерінің ведомосы")
    t = TableRows()
    for mat in MATERIALS:
        if ctx.get(S, mat) is not None:
            label, unit = lex.MATERIALS[mat]
            t.add([t.next_no, label, unit, ctx.fmt(S, mat)], {mat: 3})
    doc.add_rows(["Р/с №", "Конструкциялардың, материалдардың атауы", "Өлш. бірл.", "Саны"], t,
                 [0.09, 0.59, 0.12, 0.20], "tbl_materials")

    total = ctx.fmt(S, "concrete_total_m3")
    doc.para(f"Монолитті бетонның жалпы шығыны {total} м³ құрайды.", {"concrete_total_m3": total})
    return doc
