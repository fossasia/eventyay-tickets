all: localecompile staticfiles
production: localecompile staticfiles compress
LNGS:=`find eventyay/locale/ -mindepth 1 -maxdepth 1 -type d -printf "-l %f "`

localecompile:
	./manage.py compilemessages

localegen:
	./manage.py makemessages --keep-pot --ignore "eventyay/helpers/*" --ignore "eventyay/static/npm_dir/*" $(LNGS)
	./manage.py makemessages --keep-pot -d djangojs --ignore "eventyay/static/npm_dir/*" --ignore "eventyay/helpers/*" --ignore "eventyay/static/jsi18n/*" --ignore "eventyay/static/jsi18n/*" --ignore "eventyay/static.dist/*" --ignore "data/*" --ignore "eventyay/static/rrule/*" --ignore "build/*" $(LNGS)

staticfiles: jsi18n
	./manage.py collectstatic --noinput

compress: npminstall
	./manage.py compress

jsi18n: localecompile
	./manage.py compilejsi18n

test:
	py.test tests

coverage:
	coverage run -m py.test

npminstall:
	# keep this in sync with setup.py!
	mkdir -p eventyay/static.dist/node_prefix/
	cp -r eventyay/static/npm_dir/* eventyay/static.dist/node_prefix/
	npm install --prefix=eventyay/static.dist/node_prefix

