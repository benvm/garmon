@INTLTOOL_XML_RULE@
@INTLTOOL_DESKTOP_RULE@
@INTLTOOL_SCHEMAS_RULE@

Accessoriesdir = $(datadir)/applications
Accessories_in_files = garmon.desktop.in
Accessories_DATA = $(Accessories_in_files:.desktop.in=.desktop)

schemadir = $(GCONF_SCHEMA_FILE_DIR)
schema_in_files = garmon.schemas.in
schema_DATA = $(schema_in_files:.schemas.in=.schemas)


install-data-local: $(schema_DATA)
if GCONF_SCHEMAS_INSTALL
	if test -z "$(DESTDIR)" ; then \
	for p in $^ ; do \
	GCONF_CONFIG_SOURCE=$(GCONF_SCHEMA_CONFIG_SOURCE) $(GCONFTOOL) --makefile-install-rule $$p 2>&1 > /dev/null; \
	done \
	fi
endif




icondir = $(datadir)/icons/hicolor/48x48/apps
icon_DATA = garmon.png
svgicondir = $(datadir)/icons/hicolor/scalable/apps
svgicon_DATA = garmon.svg

gtk_update_icon_cache = gtk-update-icon-cache -f -t $(datadir)/icons/hicolor

install-data-hook: update-icon-cache
uninstall-hook: update-icon-cache
update-icon-cache:
	@-if test -z "$(DESTDIR)"; then \
	echo "Updating Gtk icon cache."; \
		$(gtk_update_icon_cache); \
	else \
		echo "*** Icon cache not updated.  After (un)install, run this:"; \
		echo "***   $(gtk_update_icon_cache)"; \
	fi

garmon_pixmapsdir = $(pkgdatadir)/pixmaps

garmon_pixmaps_DATA = \
	garmon.svg \
	garmon.png 

gladedir = $(pkgdatadir)/glade

glade_DATA = prefs.glade
	
			
EXTRA_DIST = $(schema_DATA) \
			$(schema_in_files) \
			$(Accessories_in_files) \
			$(garmon_pixmaps_DATA) \
			$(icon_DATA) \
			$(svgicon_DATA) \
			$(glade_DATA)
			
             
CLEANFILES = garmon.desktop garmon.desktop.in

DISTCLEANFILES = $(schema_in_files:.schemas.in=.schemas) \
                 $(Accessories_in_files:.desktop.in=.desktop)

