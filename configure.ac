dnl Process this file with autoconf to produce a configure script.
dnl Created by Anjuta application wizard.

m4_define(garmon_major_version,  0)
m4_define(garmon_minor_version, 3)
m4_define(garmon_micro_version,  0)
m4_define(garmon_version, garmon_major_version.garmon_minor_version.garmon_micro_version)

AC_INIT(garmon, garmon_version)
AM_INIT_AUTOMAKE(AC_PACKAGE_NAME, AC_PACKAGE_VERSION)
AM_CONFIG_HEADER(config.h)
AM_MAINTAINER_MODE


GETTEXT_PACKAGE=garmon
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE(GETTEXT_PACKAGE,"$GETTEXT_PACKAGE", [GETTEXT package name])
AM_GLIB_GNU_GETTEXT
#AC_CHECK_FUNC(bind_textdomain_codeset,,[AC_CHECK_LIB(intl,bind_textdomain_codeset)])
IT_PROG_INTLTOOL([0.35.0])

AM_PATH_PYTHON
AM_CHECK_PYMOD(serial,,,[AC_MSG_ERROR(Please install the pyserial module)])


PKG_CHECK_MODULES(PYGTK, pygtk-2.0)

AC_SUBST(VERSION)
AC_SUBST(PACKAGE)

AS_AC_EXPAND(GARMON_VERSION, $VERSION)
AS_AC_EXPAND(PYTHONDIR, $pythondir)
AS_AC_EXPAND(PLUGINDIR, $pythondir/$PACKAGE/plugins)
AS_AC_EXPAND(PKGDATADIR, $datarootdir/$PACKAGE)
AS_AC_EXPAND(UIDIR, $datarootdir/$PACKAGE/ui)
AS_AC_EXPAND(ICONSDIR, $datarootdir/icons/hicolor)
AS_AC_EXPAND(PIXMAPDIR, $datarootdir/pixmaps/$PACKAGE)

AC_OUTPUT([
Makefile
garmon/Makefile
garmon/defs.py
garmon/garmon
data/Makefile
data/garmon.desktop.in
plugins/Makefile
plugins/dashboard/Makefile
plugins/dtc_clearer/Makefile
plugins/dtc_reader/Makefile
plugins/live_data/Makefile
plugins/freeze_frame_data/Makefile
po/Makefile.in
])
