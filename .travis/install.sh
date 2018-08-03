#!/bin/sh
set -e
set -u

pip install -U pip setuptools wheel

if [ $TOXENV = "docs" ]; then
    sudo apt-get install enchant myspell-en-gb
fi
