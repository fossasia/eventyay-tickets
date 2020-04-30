# server component

## development setup

Install dependencies

	$ pip install -r requirements.txt

To auto-format:

	$ black venueless tests
	$ isort -rc venueless tests
	$ flake8 venueless tests

To automatically check before commits, add a script like the following to ``.git/hooks/pre-commit`` and apply ``chmod +x .git/hooks/pre-commit``:

	#!/bin/bash
	source ~/.virtualenvs/venueless/bin/activate
	cd server
	for file in $(git diff --cached --name-only | grep -E '\.py$' | grep -Ev "migrations|venueless/settings\.py|testutils/settings\.py|tests/settings\.py|venueless/core/models/__init__\.py")
	do
	  echo Scanning $file
	  git show ":$file" | black -q --check - || { echo "Black failed."; exit 1; } # we only want to lint the staged changes, not any un-staged changes
	  git show ":$file" | flake8 - --stdin-display-name="$file" || exit 1 # we only want to lint the staged changes, not any un-staged changes
	  git show ":$file" | isort -df --check-only - | grep ERROR && exit 1 || true
	done

