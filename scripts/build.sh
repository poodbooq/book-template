#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

format="${1:-pdf}"

check_draft() {
    local file="$1"
    sed -n '/^---$/,/^---$/p' "$file" | grep -q '^status: draft'
}

extract_scenes() {
    local file="$1"
    grep -oP '!\[\[\K[^\]]+' "$file" || true
}

strip_frontmatter() {
    awk 'BEGIN{c=0} /^---$/{c++; next} c>=2{print}'
}

build_chapter() {
    local ch="$1"
    local title
    title=$(sed -n '/^---$/,/^---$/p' "$ch" | grep '^title:' | sed 's/^title: *"\?\(.*\)"\?/\1/' | head -1)

    echo
    echo "# $title"
    echo

    while IFS= read -r scene_slug; do
        [ -z "$scene_slug" ] && continue
        local scene_file="${ROOT_DIR}/scenes/${scene_slug}.md"
        if [ -f "$scene_file" ]; then
            if check_draft "$scene_file"; then
                echo "[skipped (draft): $scene_slug]" >&2
                continue
            fi
            strip_frontmatter "$scene_file"
            echo
        else
            echo "[missing scene: $scene_slug]" >&2
        fi
    done < <(extract_scenes "$ch")
}

main() {
    local output_file="${ROOT_DIR}/build/book.${format}"
    mkdir -p "${ROOT_DIR}/build"
    local tmpfile
    tmpfile=$(mktemp)
    trap "rm -f $tmpfile" EXIT

    {
        local has_content=false
        for ch in "${ROOT_DIR}/chapters/"*.md; do
            [ -f "$ch" ] || continue
            if check_draft "$ch"; then
                echo "[skipped (draft): $(basename "$ch")]" >&2
                continue
            fi
            build_chapter "$ch"
            has_content=true
        done
        if ! $has_content; then
            echo "No chapters to build." >&2
            exit 1
        fi
    } > "$tmpfile"

    case "$format" in
        pdf)
            pandoc "$tmpfile" -o "$output_file" \
                --metadata title="Book" \
                --from markdown \
                --to pdf
            ;;
        html)
            pandoc "$tmpfile" -o "$output_file" \
                --metadata title="Book" \
                --from markdown \
                --to html \
                --standalone
            ;;
        *)
            echo "Unknown format: $format" >&2
            exit 1
            ;;
    esac

    echo "Built: $output_file"
}

main "$@"
