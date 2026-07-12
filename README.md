# book-template

Markdown-first шаблон для написання художніх книг із `zk`, `just`, Pandoc та AI-агентами. Файли є джерелом істини; базовий workflow не залежить від конкретного редактора.

## Основна модель

```text
scenes/       атомарні сцени з текстом
chapters/     порядок сцен у главах через [[wikilinks]]
characters/   картки персонажів
world/        локації
events/       події світу книги
notes/        research, worldbuilding, референси та ідеї
journal/      щоденник роботи
inbox/        сирі нотатки
assets/       обкладинка та інші ресурси
styles/       CSS для HTML, EPUB і PDF
```

Глави не дублюють прозу. Їхнє тіло — впорядкований список сцен:

```markdown
- [[opening-scene]]
- [[meeting-at-mill]]
```

Звичайні `[[...]]`, а не `![[...]]`, потрібні для коректних backlinks у `zk`. Під час експорту wikilinks автоматично перетворюються на читабельний текст.

## Створення книги з шаблону

Найпростіше — натиснути **Use this template** на GitHub. Через `gh`:

```bash
gh repo create my-book \
  --private \
  --template poodbooq/book-template \
  --clone
cd my-book
```

Так зберігається чиста історія нового репозиторію без ручного видалення `.git`.

## Вимоги

- Python ≥ 3.11
- [zk](https://github.com/zk-org/zk)
- [Pandoc](https://pandoc.org/)
- [just](https://github.com/casey/just)
- Python-пакети з `requirements.txt`: PyYAML і WeasyPrint

Python-залежності встановлюються у user space:

```bash
just setup
just doctor
just test
```

`WeasyPrint` є PDF engine за замовчуванням і нормально працює з українським Unicode. Інший engine можна вказати в `book.yaml`.

## Перші 10 хвилин

### 1. Заповни метадані книги

Відредагуй `book.yaml`:

```yaml
title: "Моя книга"
author: "Ім'я автора"
lang: uk-UA
rights: "© 2026 Ім'я автора"
toc: true
pdf-engine: weasyprint
```

### 2. Створи персонажа, сцену й главу

```bash
just new-character "Марта"
just new-scene "Зустріч біля млина"
just new-chapter "Глава перша"
```

Команди друкують створені шляхи. `zk` транслітерує українські назви у slug.

Альтернативний прямий синтаксис `zk`:

```bash
zk new scenes --title "Зустріч біля млина"
zk new chapters --title "Глава перша"
```

### 3. Додай сцену до глави

Використай slugs із назв файлів:

```bash
just add-scene glava-persha zustrich-bilia-mlina
```

Або додай у файл глави вручну:

```markdown
- [[zustrich-bilia-mlina]]
```

### 4. Переведи готовий текст із draft

Нові сцени й глави мають `status: draft` і не експортуються. Коли матеріал готовий до читання, зміни статус:

```yaml
status: revised
```

Статуси:

| Статус | Експортується | Значення |
|---|---:|---|
| `draft` | ні | чернетка |
| `revised` | так | робоча відредагована версія |
| `final` | так | фінальна версія; ставити свідомо |

### 5. Перевір і збери

```bash
just wordcount
just index
just check
just build-html
just build-epub
just build-pdf
```

Результати з'являться в `build/`. `just build-all` створює всі три читацькі формати.

## Основні команди

| Команда | Призначення |
|---|---|
| `just doctor` | перевірити інструменти, Python-пакети, PDF engine і конфіг `zk` |
| `just check` | перевірити YAML, статуси, slugs, links, порядок глав і сцени |
| `just test` | запустити regression та end-to-end тести |
| `just wordcount` | оновити `word-count` без переписування решти frontmatter |
| `just stats` | статистика проєкту |
| `just list-drafts` | список draft-сцен і глав |
| `just chapters` | глави в порядку експорту та кількість сцен |
| `just characters` | персонажі, ролі й арки |
| `just act 1` | нотатки з `act: 1` |
| `just pov marta` | нотатки з відповідним POV |
| `just setting old-mill` | нотатки з відповідним setting |
| `just era dark-ages` | нотатки відповідної епохи |
| `just tags` | частота тегів |
| `just timeline` | сцени й події, відсортовані за машинним порядком |
| `just search "текст"` | literal case-insensitive пошук |
| `just recent 14` | файли, змінені за останні 14 днів |
| `just index` | згенерувати актуальний `index.md` |

## Правила цілісності

`just check` блокує збірку, якщо знаходить:

- дублікати slug у різних директоріях;
- broken wikilinks;
- невідомий або відсутній `status` у сцені/главі;
- нечисловий або дубльований `order` глави;
- посилання глави не на сцену;
- порожню опубліковану сцену чи главу.

Опублікована сцена, не додана до жодної глави, є warning. Відсутня сцена або typo в status ніколи не призводять до «успішної», але неповної книги.

Повна схема frontmatter і різниця між `created`, `story-date` та `timeline-order` описані в [`SCHEMA.md`](SCHEMA.md).

## Wikilinks

- `[[slug]]` під час експорту стає назвою цільової нотатки;
- `[[slug|текст]]` стає заданим текстом;
- у прозі посилання ставиться лише на перше входження сутності;
- backlinks: `zk backlinks slug`;
- сирий синтаксис wikilinks не потрапляє в HTML, EPUB або PDF.

## AI-агенти

У `.agents/skills/` є окремі workflows для:

- brainstorming;
- діалогова лабораторія (`dialogue-lab`) — діалоги й полілоги для пошуку сюжетного руху;
- персонажів;
- continuity review;
- research;
- wikilinks;
- worldbuilding;
- написання сцен.

Скіли підпорядковуються структурі й схемі цього репозиторію. Сам шаблон повністю придатний до ручної роботи без AI.

## Платформи та редактор

Основні операції реалізовані в Python, а `justfile` лише надає короткі команди. Шаблон перевіряється на Linux; Pandoc, Python, `zk` та `just` також доступні на macOS.

`zk` використовує `$EDITOR`; редактор не захардкоджений. Наприклад:

```bash
export EDITOR=nvim
```

## Ліцензія

MIT
