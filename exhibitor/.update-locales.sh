#!/bin/sh

# Check if 'wlc' command is available
if ! command -v wlc >/dev/null 2>&1; then
    echo "Error: 'wlc' command not found. Please install it before running this script."
    exit 1
fi

COMPONENTS=pretix/pretix-plugin-exhibitors
DIR=exhibitors/locale
# Renerates .po files used for translating the plugin
set -e
set -x

# Lock Weblate
for c in $COMPONENTS; do
	wlc lock $c;
done

# Push changes from Weblate to GitHub
for c in $COMPONENTS; do
	wlc commit $c;
done

# Pull changes from GitHub
git pull --rebase

# Update po files itself
make localegen

# Commit changes
git add $DIR/*/*/*.po
git add $DIR/*.pot

git commit -s -m "Update po files
[CI skip]"

# Push changes
git push

# Unlock Weblate
for c in $COMPONENTS; do
	wlc unlock $c;
done
