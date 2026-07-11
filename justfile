set shell := ["/bin/bash", "-c"]

build-pdf:
    @scripts/build.sh pdf

build-html:
    @scripts/build.sh html

wordcount:
    #!/bin/bash
    total=0
    count=0
    for f in scenes/*.md; do
        [ -f "$f" ] || continue
        # strip frontmatter before counting
        wc_body=$(awk 'BEGIN{c=0} /^---$/{c++; next} c>=2{print}' "$f" | wc -w)
        total=$((total + wc_body))
        count=$((count + 1))
        printf "%8d  %s\n" "$wc_body" "$(basename "$f")"
        sed -i "0,/^word-count:/s/^word-count:.*/word-count: $wc_body/" "$f"
    done
    echo "---------------------"
    printf "%8d  total (%d scenes)\n" "$total" "$count"

list-drafts:
    #!/bin/bash
    echo "=== Draft chapters ==="
    for f in chapters/*.md; do
        [ -f "$f" ] || continue
        if sed -n '/^---$/,/^---$/p' "$f" | grep -q '^status: draft'; then
            echo "  $f"
        fi
    done
    echo ""
    echo "=== Draft scenes ==="
    for f in scenes/*.md; do
        [ -f "$f" ] || continue
        if sed -n '/^---$/,/^---$/p' "$f" | grep -q '^status: draft'; then
            echo "  $f"
        fi
    done

act N:
    #!/bin/bash
    N="{{N}}"
    for f in scenes/*.md; do
        [ -f "$f" ] || continue
        if sed -n '/^---$/,/^---$/p' "$f" | grep -q "act:.*$N"; then
            title=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^title:' | sed 's/^title: *"\(.*\)"$/\1/' | head -1)
            wc=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^word-count:' | grep -oP '\d+' | head -1)
            printf "%8s  %s\n" "${wc:-0}" "$title"
        fi
    done

pov CHAR:
    #!/bin/bash
    CHAR="{{CHAR}}"
    for f in scenes/*.md; do
        [ -f "$f" ] || continue
        if sed -n '/^---$/,/^---$/p' "$f" | grep -q "pov:.*$CHAR"; then
            title=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^title:' | sed 's/^title: *"\(.*\)"$/\1/' | head -1)
            printf "  %s\n" "$title"
        fi
    done

setting LOC:
    #!/bin/bash
    LOC="{{LOC}}"
    for f in scenes/*.md; do
        [ -f "$f" ] || continue
        if sed -n '/^---$/,/^---$/p' "$f" | grep -q "setting:.*$LOC"; then
            title=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^title:' | sed 's/^title: *"\(.*\)"$/\1/' | head -1)
            printf "  %s\n" "$title"
        fi
    done

era ERA:
    #!/bin/bash
    ERA="{{ERA}}"
    for f in events/*.md; do
        [ -f "$f" ] || continue
        if sed -n '/^---$/,/^---$/p' "$f" | grep -q "era:.*$ERA"; then
            title=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^title:' | sed 's/^title: *"\(.*\)"$/\1/' | head -1)
            date=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^date:' | sed 's/^date: *"\?\(.*\)"\?/\1/' | head -1)
            printf "%-20s  %s\n" "$date" "$title"
        fi
    done | sort

stats:
    #!/bin/bash
    drafts=0; revised=0; final=0
    for f in scenes/*.md; do
        [ -f "$f" ] || continue
        status=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^status:' | sed 's/^status: //' | head -1)
        case "$status" in
            draft) drafts=$((drafts + 1)) ;;
            revised) revised=$((revised + 1)) ;;
            final) final=$((final + 1)) ;;
        esac
    done
    total_scenes=$((drafts + revised + final))
    echo "Scenes:  $total_scenes"
    echo "  draft:    $drafts"
    echo "  revised:  $revised"
    echo "  final:    $final"
    ch_count=$(ls chapters/*.md 2>/dev/null | wc -l)
    char_count=$(ls characters/*.md 2>/dev/null | wc -l)
    ev_count=$(ls events/*.md 2>/dev/null | wc -l)
    loc_count=$(ls world/*.md 2>/dev/null | wc -l)
    echo ""
    echo "Chapters:   $ch_count"
    echo "Characters: $char_count"
    echo "Events:     $ev_count"
    echo "Locations:  $loc_count"

chapters:
    #!/bin/bash
    for ch in chapters/*.md; do
        [ -f "$ch" ] || continue
        title=$(sed -n '/^---$/,/^---$/p' "$ch" | grep '^title:' | sed 's/^title: *"\(.*\)"$/\1/' | head -1)
        sc_count=$(grep -c '!\[\[' "$ch" 2>/dev/null || echo 0)
        printf "%-30s  %2d scenes\n" "$title" "$sc_count"
    done

characters:
    #!/bin/bash
    for f in characters/*.md; do
        [ -f "$f" ] || continue
        title=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^title:' | sed 's/^title: *"\(.*\)"$/\1/' | head -1)
        role=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^role:' | sed 's/^role: *"\?\(.*\)"\?/\1/' | head -1)
        arc=$(sed -n '/^---$/,/^---$/p' "$f" | grep '^arc:' | sed 's/^arc: *"\?\(.*\)"\?/\1/' | head -1)
        printf "%-20s  %-12s  %s\n" "$title" "${role:--}" "${arc:--}"
    done | sort

tags:
    #!/bin/bash
    for f in */*.md; do
        [ -f "$f" ] || continue
        sed -n '/^---$/,/^---$/p' "$f" | grep '^tags:' | sed 's/^tags: *\[//;s/\]//;s/,/\n/g;s/ *//g' | grep -v '^$'
    done | sort | uniq -c | sort -rn

search QUERY:
    #!/bin/bash
    grep -rn --include='*.md' "{{QUERY}}" scenes/ chapters/ characters/ world/ events/ journal/ inbox/ notes/

recent DAYS="7":
    #!/bin/bash
    find scenes/ chapters/ characters/ world/ events/ journal/ inbox/ notes/ -name '*.md' -mtime -{{DAYS}} | sort
