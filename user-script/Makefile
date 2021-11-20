.PHONY: default build

DIST_FILES = $(patsubst %.ts,dist/%.js,$(wildcard *.ts))

default: build

scripts/.sentinel: *.ts
	cd scripts && pnpx tsc
	touch $@

build:
	pnpx ts-node-script ./scripts/build.ts

