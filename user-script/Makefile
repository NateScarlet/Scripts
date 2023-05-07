.PHONY: default build

DIST_FILES = $(patsubst %.ts,dist/%.js,$(wildcard *.ts))

default: build

scripts/.sentinel: *.ts
	cd scripts && pnpm exec tsc
	touch $@

assets/style.css: *.ts
	NODE_ENV=production pnpm exec tailwindcss --minify -o ./assets/style.css

build:
	pnpm exec ts-node-script ./scripts/build.ts

