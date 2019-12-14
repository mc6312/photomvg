packer = 7z
pack = $(packer) a -mx=9
arcx = .7z
docs = COPYING Changelog README.md
srcversion = pmvgcommon
version = $(shell python3 -c 'from $(srcversion) import VERSION; print(VERSION)')
title_version = $(shell python3 -c 'from $(srcversion) import TITLE_VERSION; print(TITLE_VERSION)')
branch = $(shell git symbolic-ref --short HEAD)
basename = photomvg
zipname = $(basename).zip
arcname = $(basename)$(arcx)
srcarcname = $(basename)-src$(arcx)
srcs = __main__.py photomvg.py gtktools.py photomvg.ui pmvg*.py pmvg*.ui images/*
backupdir = ~/shareddocs/pgm/python/

app:
	$(pack) -tzip $(zipname) $(srcs)
	@echo '#!/usr/bin/env python3' >$(basename)
	@cat $(zipname) >>$(basename)
	rm $(zipname)
	chmod 755 $(basename)

archive:
	$(pack) $(srcarcname) *.py *. Makefile *.geany *.ui *.svg images/* $(docs)
distrib:
	make app
	$(pack) $(basename)-$(version)$(arcx) $(basename) $(docs)
backup:
	make archive
	mv $(srcarcname) $(backupdir)
update:
	$(packer) x -y $(backupdir)$(srcarcname)
commit:
	git commit -a -uno -m "$(version)"
docview:
	$(eval docname = README.htm)
	@echo "<html><head><meta charset="utf-8"><title>$(title_version) README</title></head><body>" >$(docname)
	markdown_py README.md >>$(docname)
	@echo "</body></html>" >>$(docname)
	x-www-browser $(docname)
	#rm $(docname)
show-branch:
	@echo "$(branch)"
