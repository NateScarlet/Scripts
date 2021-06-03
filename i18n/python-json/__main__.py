from . import i18n

print(i18n.t("test1"))
print(i18n.t("test2"))
print(i18n.t("test3"))

i18n.set_language("zh")

print(i18n.t("test1"))
print(i18n.t("test2"))
print(i18n.t("test3"))
