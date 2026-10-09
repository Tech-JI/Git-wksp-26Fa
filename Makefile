UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
  PDF_FONT := Helvetica Neue
  FONT_FALLBACK :=
else ifeq ($(UNAME_S),Linux)
  PDF_FONT := DejaVu Sans
  FONT_FALLBACK :=
else
  PDF_FONT := Segoe UI
  FONT_FALLBACK := -V mainfontfallback="Segoe UI Emoji:mode=harf"
endif

build:
	@pandoc --pdf-engine=xelatex -t beamer -F mermaid-filter --slide-level=2 --toc-depth=1 --syntax-highlighting=idiomatic -o part1.pdf part1.md
	@pandoc --pdf-engine=xelatex --syntax-highlighting=tango -V colorlinks=true -V linkcolor=blue -V urlcolor=blue -o ssh_setup.pdf ssh_setup.md
	@pandoc --pdf-engine=lualatex -V mainfont="$(PDF_FONT)" $(FONT_FALLBACK) -o worksheet.pdf worksheet.md
	@echo Build success.
