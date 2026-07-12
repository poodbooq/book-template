set shell := ["/bin/bash", "-c"]

book := "python3 scripts/book.py"

default:
    @just --list

setup:
    python3 -m pip install --user -r requirements.txt

check:
    @{{ book }} check

doctor:
    @{{ book }} doctor

test:
    python3 -m unittest discover -s tests -v

build-markdown: check
    @{{ book }} build markdown

build-html: check
    @{{ book }} build html

build-epub: check
    @{{ book }} build epub

build-pdf: check
    @{{ book }} build pdf

build-all: build-html build-epub build-pdf

wordcount:
    @{{ book }} wordcount

index:
    @{{ book }} index

stats:
    @{{ book }} stats

list-drafts:
    @{{ book }} list-drafts

chapters:
    @{{ book }} chapters

characters:
    @{{ book }} characters

tags:
    @{{ book }} tags

timeline:
    @{{ book }} timeline

search QUERY:
    @{{ book }} search {{ quote(QUERY) }}

recent DAYS="7":
    @{{ book }} recent {{ quote(DAYS) }}

act N:
    @{{ book }} query act {{ quote(N) }}

pov CHAR:
    @{{ book }} query pov {{ quote(CHAR) }}

setting LOC:
    @{{ book }} query setting {{ quote(LOC) }}

era ERA:
    @{{ book }} query era {{ quote(ERA) }}

new-scene TITLE:
    @{{ book }} new scene {{ quote(TITLE) }}

new-chapter TITLE:
    @{{ book }} new chapter {{ quote(TITLE) }}

new-character TITLE:
    @{{ book }} new character {{ quote(TITLE) }}

new-location TITLE:
    @{{ book }} new location {{ quote(TITLE) }}

new-event TITLE:
    @{{ book }} new event {{ quote(TITLE) }}

new-note TITLE:
    @{{ book }} new note {{ quote(TITLE) }}

new-inbox TITLE:
    @{{ book }} new inbox {{ quote(TITLE) }}

new-journal:
    @{{ book }} new journal

add-scene CHAPTER SCENE:
    @{{ book }} add-scene {{ quote(CHAPTER) }} {{ quote(SCENE) }}
