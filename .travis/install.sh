#!/bin/bash
set -e
set -u

pip install -U pip setuptools wheel tox

if [ $TOXENV = "docs" ]; then
    sudo apt-get install enchant myspell-en-gb
    echo "Installed spellcheck dependencies"
fi

if [[ "$TOXENV" = *"mysql"* ]]; then
    mysql -u root -e 'CREATE DATABASE pretalx DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci;'
    echo "Created database"
fi

if [[ "$TOXENV" = *"postgres"* ]]; then
    psql -c 'create database travis_ci_test;' -U postgres
    echo "Created database"
fi
