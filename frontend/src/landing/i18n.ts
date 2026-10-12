// Тексты лендинга. KZ написан сразу; перед публикацией его вычитывает носитель языка.
// Числа в тексты не пишутся: они приходят из content.ts через {переменные}.
import { createContext, useCallback, useEffect, useState } from "react";

export type Lang = "ru" | "kz";

export const RU = {
  "nav.how": "Как работает",
  "nav.research": "Исследование",
  "nav.login": "Войти",
  "nav.open": "Открыть платформу",
  "hero.title": "Сверка технико-экономических показателей проекта",
  "hero.lead": "ПЗ, АР, КР и смета на русском и казахском: расхождения находятся за минуты и обводятся прямо на странице документа.",
  "hero.demo": "Попробовать демо",
  "hero.login": "Войти",
  "problem.title": "Ручная сверка — это часы и пропущенные ошибки",
  "problem.lead": "Один и тот же показатель встречается в нескольких разделах проекта, и эксперт сверяет их вручную.",
  "problem.sections": "раздела проекта сверяются между собой",
  "problem.fields": "ключевых ТЭП извлекается автоматически",
  "problem.types": "видов несоответствий проверяет сервис",
  "how.title": "Как это работает",
  "how.step1.title": "Загрузите документы",
  "how.step1.text": "ПЗ, текстовые части АР и КР, сметная документация — PDF или DOCX, на русском или казахском.",
  "how.step2.title": "Сервис извлекает ТЭП",
  "how.step2.text": "Показатели из текста и таблиц — по каждому зданию, со ссылкой на страницу.",
  "how.step3.title": "Сверяет разделы",
  "how.step3.text": "Расхождения обводятся на странице документа; эксперт подтверждает или отклоняет каждое.",
  "example.title": "Посмотрите отчёт сами",
  "example.lead": "Настоящий интерфейс на демонстрационном пакете: выберите замечание — значение обведётся на странице.",
  "example.open": "Открыть демо на весь экран",
  "checks.title": "Что проверяется",
  "checks.lead": "Проверки, которые сервис выполняет сейчас.",
  "checks.scanNote": "На сканах без текстового слоя таблицы распознаются ненадёжно: отмеченные проверки там ограничены.",
  "langs.title": "Русский и қазақ тілі",
  "langs.lead": "Один и тот же показатель находится в документах на обоих языках.",
  "langs.ru": "Общая площадь здания — {value} м²",
  "langs.kz": "Ғимараттың жалпы ауданы — {value} м²",
  "research.title": "Исследование",
  "research.lead": "Сервис — часть дипломной работы: извлечение ТЭП и поиск несоответствий проверены на синтетических пакетах и на реальной документации.",
  "research.extraction": "F1 извлечения ТЭП на скрытых формулировках ({set})",
  "research.detectors": "F1 детекторов несоответствий ({set})",
  "research.real": "реальная ОПЗ: ТЭП найдено {tep}, размеченных находок — {findings}, ложных — {fp}",
  "research.limits": "Ограничения: реальный документ пока один, сканы без текстового слоя распознаются ненадёжно, казахские формулировки покрыты хуже русских.",
  "research.source": "Источник: README репозитория, разделы оценки",
  "security.title": "Данные под контролем",
  "security.invite": "Доступ только по приглашению",
  "security.own": "Каждый видит только свои проверки",
  "security.retention": "Проверки и файлы удаляются через {n} дней",
  "security.noLlm": "Документы не отправляются в сторонние ИИ-сервисы",
  "access.title": "Запросить доступ",
  "access.lead": "Оставьте почту — администратор создаст аккаунт и пришлёт приглашение.",
  "access.email": "Почта",
  "access.org": "Организация",
  "access.comment": "Комментарий",
  "access.send": "Отправить заявку",
  "access.sending": "Отправляем…",
  "access.done": "Спасибо! Заявка отправлена, мы напишем на указанную почту.",
  "footer.thesis": "Дипломный проект: автоматическое извлечение и сверка ТЭП в проектной документации (RU/KZ).",
  "footer.github": "Исходный код",
  "scene.alt": "Здание в линиях расходится на этажи ПЗ, АР, КР и смета; несовпадающие значения общей площади обведены красным.",
  "type.AREA_PZ_VS_AR_EXPLICATION": "Площадь в ПЗ и экспликации АР",
  "type.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE": "Объёмы материалов в КР и локальной смете",
  "type.COST_OBJECT_ESTIMATE_VS_SUMMARY": "Объектная смета и сводный сметный расчёт",
  "type.MISSING_MANDATORY_TEP": "Обязательный ТЭП отсутствует",
  "type.TEP_CROSS_SECTION_MISMATCH": "Один ТЭП в разных разделах",
  "type.TABLE_TOTAL_MISMATCH": "Итог таблицы не равен сумме строк",
  "type.VALUE_CROSS_SECTION_MISMATCH": "Одно значение в разных местах ПЗ",
  "type.PARAMETER_CONTRADICTION": "Противоречие параметров здания",
  "type.TEP_CALCULATION_METHOD": "Метод расчёта показателя",
  "type.GEOMETRY_INCONSISTENCY": "Геометрическая несогласованность",
  "type.COPY_PASTE_LABEL": "Чужая подпись (копирование)",
} as const;

export type LKey = keyof typeof RU;

export const KZ: Record<LKey, string> = {
  "nav.how": "Қалай жұмыс істейді",
  "nav.research": "Зерттеу",
  "nav.login": "Кіру",
  "nav.open": "Платформаны ашу",
  "hero.title": "Жобаның техникалық-экономикалық көрсеткіштерін салыстыру",
  "hero.lead": "ТЖ, СШ, КШ және смета орыс және қазақ тілдерінде: сәйкессіздіктер бірнеше минутта табылып, құжат бетінде белгіленеді.",
  "hero.demo": "Демоны көру",
  "hero.login": "Кіру",
  "problem.title": "Қолмен салыстыру — сағаттар мен жіберілген қателер",
  "problem.lead": "Бір көрсеткіш жобаның бірнеше бөлімінде кездеседі, сарапшы оларды қолмен салыстырады.",
  "problem.sections": "жоба бөлімі өзара салыстырылады",
  "problem.fields": "негізгі ТЭК автоматты түрде алынады",
  "problem.types": "сәйкессіздік түрін сервис тексереді",
  "how.title": "Бұл қалай жұмыс істейді",
  "how.step1.title": "Құжаттарды жүктеңіз",
  "how.step1.text": "ТЖ, СШ және КШ мәтіндік бөліктері, сметалық құжаттама — PDF немесе DOCX, орыс немесе қазақ тілінде.",
  "how.step2.title": "Сервис ТЭК-ті алады",
  "how.step2.text": "Мәтін мен кестелердегі көрсеткіштер — әр ғимарат бойынша, бетке сілтемемен.",
  "how.step3.title": "Бөлімдерді салыстырады",
  "how.step3.text": "Сәйкессіздіктер құжат бетінде белгіленеді; сарапшы әрқайсысын растайды немесе қабылдамайды.",
  "example.title": "Есепті өзіңіз қараңыз",
  "example.lead": "Демонстрациялық пакеттегі нақты интерфейс: ескертуді таңдаңыз — мән бетте белгіленеді.",
  "example.open": "Демоны толық экранда ашу",
  "checks.title": "Не тексеріледі",
  "checks.lead": "Сервис қазір орындайтын тексерулер.",
  "checks.scanNote": "Мәтін қабаты жоқ сканерлерде кестелер сенімсіз танылады: белгіленген тексерулер онда шектеулі.",
  "langs.title": "Орыс тілі және қазақ тілі",
  "langs.lead": "Бір көрсеткіш екі тілдегі құжаттардан да табылады.",
  "langs.ru": "Общая площадь здания — {value} м²",
  "langs.kz": "Ғимараттың жалпы ауданы — {value} м²",
  "research.title": "Зерттеу",
  "research.lead": "Сервис — дипломдық жұмыстың бөлігі: ТЭК алу және сәйкессіздіктерді іздеу синтетикалық пакеттерде және нақты құжаттамада тексерілді.",
  "research.extraction": "Жасырын тұжырымдардағы ТЭК алудың F1 мәні ({set})",
  "research.detectors": "Сәйкессіздік детекторларының F1 мәні ({set})",
  "research.real": "нақты ТЖ: табылған ТЭК {tep}, белгіленген табылымдар — {findings}, жалған — {fp}",
  "research.limits": "Шектеулер: нақты құжат әзірге біреу, мәтін қабаты жоқ сканерлер сенімсіз танылады, қазақша тұжырымдар орысшадан нашар қамтылған.",
  "research.source": "Дереккөз: репозиторийдің README файлы, бағалау бөлімдері",
  "security.title": "Деректер бақылауда",
  "security.invite": "Қол жеткізу тек шақыру бойынша",
  "security.own": "Әркім тек өз тексерулерін көреді",
  "security.retention": "Тексерулер мен файлдар {n} күннен кейін жойылады",
  "security.noLlm": "Құжаттар бөгде ЖИ-сервистерге жіберілмейді",
  "access.title": "Қол жеткізуді сұрау",
  "access.lead": "Поштаңызды қалдырыңыз — әкімші аккаунт ашып, шақыру жібереді.",
  "access.email": "Пошта",
  "access.org": "Ұйым",
  "access.comment": "Түсініктеме",
  "access.send": "Өтінім жіберу",
  "access.sending": "Жіберілуде…",
  "access.done": "Рахмет! Өтінім жіберілді, көрсетілген поштаға жазамыз.",
  "footer.thesis": "Дипломдық жоба: жобалық құжаттамадағы ТЭК-ті автоматты түрде алу және салыстыру (RU/KZ).",
  "footer.github": "Бастапқы код",
  "scene.alt": "Сызықтардан тұратын ғимарат ТЖ, СШ, КШ және смета қабаттарына бөлінеді; жалпы ауданның сәйкес келмейтін мәндері қызылмен белгіленген.",
  "type.AREA_PZ_VS_AR_EXPLICATION": "ТЖ мен СШ экспликациясындағы аудан",
  "type.MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE": "КШ мен жергілікті сметадағы материал көлемдері",
  "type.COST_OBJECT_ESTIMATE_VS_SUMMARY": "Объектілік смета және жиынтық сметалық есеп",
  "type.MISSING_MANDATORY_TEP": "Міндетті ТЭК жоқ",
  "type.TEP_CROSS_SECTION_MISMATCH": "Әр бөлімдегі бір ТЭК",
  "type.TABLE_TOTAL_MISMATCH": "Кесте қорытындысы жолдар қосындысына тең емес",
  "type.VALUE_CROSS_SECTION_MISMATCH": "ТЖ-ның әр жеріндегі бір мән",
  "type.PARAMETER_CONTRADICTION": "Ғимарат параметрлерінің қайшылығы",
  "type.TEP_CALCULATION_METHOD": "Көрсеткішті есептеу әдісі",
  "type.GEOMETRY_INCONSISTENCY": "Геометриялық сәйкессіздік",
  "type.COPY_PASTE_LABEL": "Бөгде жазба (көшіру)",
};

const KEY = "tep.lang";
const read = (): Lang => { try { return localStorage.getItem(KEY) === "kz" ? "kz" : "ru"; } catch { return "ru"; } };

export const tlFor = (lang: Lang) => (key: LKey, vars: Record<string, string | number> = {}) =>
  (lang === "kz" ? KZ : RU)[key].replace(/\{(\w+)\}/g, (_, v) => String(vars[v] ?? ""));

export function useLang() {
  const [lang, setLangState] = useState<Lang>(read);
  useEffect(() => {
    document.documentElement.lang = lang === "kz" ? "kk" : "ru";
    return () => { document.documentElement.lang = "ru"; }; // the platform is Russian
  }, [lang]);
  const setLang = useCallback((l: Lang) => {
    try { localStorage.setItem(KEY, l); } catch { /* blocked storage */ }
    setLangState(l);
  }, []);
  const tl = useCallback(tlFor(lang), [lang]);
  return { lang, setLang, tl };
}

export const LangContext = createContext<ReturnType<typeof useLang>>({ lang: "ru", setLang: () => {}, tl: tlFor("ru") });
