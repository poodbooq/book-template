# book-template

Шаблон репозиторію для художніх книг. Працює з markdown-файлами, `zk` (Zettelkasten) та `nvim`.

## Структура

```
scenes/       — сцени (атомарні нотатки)
chapters/     — глави-збірки з ![[посиланнями]] на сцени
characters/   — картки персонажів
world/        — світобудова (локації)
events/       — події (службові, не експортуються)
journal/      — щоденник
inbox/        — сирі ідеї, швидкі нотатки
notes/        — оформлені дослідження, матеріали
```

## Вимоги

- [zk](https://github.com/zk-org/zk)
- [pandoc](https://pandoc.org/)
- [just](https://github.com/casey/just)

## Використання

```sh
# Нова сцена
zk new --title "Назва сцени" --dir scenes

# Нова глава
zk new --title "Назва глави" --dir chapters

# Збірка
just build-pdf       # book.pdf
just build-html      # book.html

# Порахувати слова
just wordcount

# Показати чернетки
just list-drafts
```

## Експорт

- `status: draft` у frontmatter сцени або глави — файл пропускається при збірці
- `status: revised` або `status: final` — експортується
- `events/`, `characters/`, `world/`, `journal/` не експортуються

## Ліцензія

MIT
