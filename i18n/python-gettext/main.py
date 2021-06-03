import gettext
import pathlib
# aaa
print(pathlib.Path(__file__).parent / 'locales')
t = gettext.translation('messages', pathlib.Path(
    __file__).parent / 'locales', fallback=True)
_ = t.gettext

print(_("test"))
print(_("test2"))
print(_("test3"))
print(_("test4"))
print(t.ngettext("test5", "test5s", 2))
print(_("test6: %s"))
