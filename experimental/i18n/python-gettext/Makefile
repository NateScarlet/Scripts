.PHONY: default

LANGUAGES = \
	zh.UTF-8 \
	jp.UTF-8

PORTABLE_OBJECTS = $(patsubst %,locales/%/LC_MESSAGES/messages.po,$(LANGUAGES))
MACHINE_OBJECTS = $(patsubst %,locales/%/LC_MESSAGES/messages.mo,$(LANGUAGES))

default: $(MACHINE_OBJECTS)

locales/messages.pot: *.py
	xgettext *.py -o $@


$(BUILD_FOLDERS): LANG=$(patsubst locales/%/LC_MESSAGES/messages.po,%,$@)
$(PORTABLE_OBJECTS): locales/messages.pot
	mkdir -p $(dir $@)
	if [ -f $@ ]; then \
		msgmerge $@ $< -o $@ ;\
	else \
		msginit --no-translator -l $(LANG) -i $< -o $@ ;\
	fi

%.mo : %.po 
	msgfmt $< -o $@
	
