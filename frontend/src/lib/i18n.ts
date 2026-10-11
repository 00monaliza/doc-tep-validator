const RU = {
  "app.name": "ТЭП·Сверка",
  "nav.checks": "Проверки", "nav.new": "Новая проверка", "nav.demo": "Демо", "nav.method": "Методика", "nav.settings": "Настройки",
  "search.placeholder": "Найти проверку или замечание…", "search.hint": "Поиск",
  "checks.count": "Мои проверки · {n}", "checks.empty": "Проверок пока нет",
  "checks.empty.body": "Загрузите ПЗ, АР, КР и смету — или посмотрите демо-отчёт.",
  "checks.col.title": "Объект", "checks.col.sections": "Разделы", "checks.col.result": "Итог",
  "checks.col.expert": "Эксперт", "checks.col.date": "Дата", "checks.col.expires": "Хранится до",
  "checks.status.pending": "идёт проверка…", "checks.status.receiving": "загрузка не завершена",
  "checks.status.uploaded": "ждёт запуска", "checks.status.error": "ошибка",
  "checks.rename": "Переименовать", "checks.rename.save": "Сохранить",
  "new.step.files": "Файлы", "new.step.sections": "Разделы", "new.step.run": "Проверка",
  "new.drop": "Перетащите ПЗ, АР, КР и смету сюда или выберите файлы", "new.drop.hint": "PDF или DOCX, до 20 файлов по 50 МБ",
  "new.uploading": "Загружаем: {sent} из {total} МБ", "new.running": "Сверяем разделы…",
  "report.tab.findings": "Замечания", "report.tab.tep": "ТЭП", "report.tab.completeness": "Комплектность",
  "report.none": "Расхождений между разделами не найдено.", "report.detail.empty": "Выберите замечание слева",
  "report.export": "Скачать XLSX", "report.split": "Рядом", "report.single": "По одному",
  "report.pending": "Идёт проверка документов…", "report.receiving": "Загрузка файлов не была завершена. Загрузите документы заново.",
  "report.error": "Проверка не выполнена: {error}", "report.missing": "Проверка не найдена или удалена.",
  "verdict.confirm": "Подтверждаю", "verdict.false": "Ложное", "verdict.comment": "Комментарий",
  "settings.theme": "Тема", "settings.theme.system": "Как в системе", "settings.theme.light": "Калька (светлая)",
  "settings.theme.dark": "Синька (тёмная)", "settings.account": "Аккаунт", "settings.password": "Сменить пароль",
  "settings.password.sent": "Письмо со ссылкой для нового пароля отправлено на вашу почту.",
  "settings.signout": "Выйти",
  "cmd.new": "Новая проверка", "cmd.export": "Скачать XLSX", "cmd.theme": "Переключить тему", "cmd.signout": "Выйти",
  "cmd.go.check": "Проверка", "cmd.go.finding": "Замечание",
} as const;

export type Key = keyof typeof RU;

export function t(key: Key, vars: Record<string, string | number> = {}): string {
  return RU[key].replace(/\{(\w+)\}/g, (_, v) => String(vars[v] ?? ""));
}
