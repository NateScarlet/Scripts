.PHONY: default build

DIST_FILES = $(patsubst %.ts,dist/%.js,$(wildcard *.ts))

default: build

scripts/.sentinel: *.ts
	cd scripts && pnpx tsc
	touch $@

build:
	NODE_ENV=production pnpx tailwindcss --minify -o ./assets/style.css
	pnpx ts-node-script ./scripts/build.ts

