@INTLTOOL_XML_RULE@
@INTLTOOL_DESKTOP_RULE@

Accessoriesdir = $(datadir)/applications
Accessories_in_files = garmon.desktop.in
Accessories_DATA = $(Accessories_in_files:.desktop.in=.desktop)

icondir = $(ICONSDIR)/48x48/apps
icon_DATA = garmon.png
svgicondir = $(ICONSDIR)/scalable/apps
svgicon_DATA = garmon.svg

gtk_update_icon_cache = gtk-update-icon-cache -f -t $(ICONSDIR)

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

garmon_pixmapsdir = $(PIXMAPDIR)

garmon_pixmaps_DATA = \
	garmon.svg \
	garmon.png 

gladedir = $(GLADEDIR)

glade_DATA = prefs.glade
	
			
EXTRA_DIST = $(Accessories_in_files) \
			$(garmon_pixmaps_DATA) \
			$(icon_DATA) \
			$(svgicon_DATA) \
			$(glade_DATA)
			
             
CLEANFILES = garmon.desktop garmon.desktop.in

DISTCLEANFILES = $(Accessories_in_files:.desktop.in=.desktop)

