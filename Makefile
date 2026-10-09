build:
	@pandoc --pdf-engine=xelatex -t beamer -F mermaid-filter --slide-level=2 --toc-depth=1 --syntax-highlighting=idiomatic -o part1.pdf part1.md
	@pandoc --pdf-engine=xelatex --syntax-highlighting=tango -V colorlinks=true -V linkcolor=blue -V urlcolor=blue -o ssh_setup.pdf ssh_setup.md
	@pandoc --pdf-engine=lualatex -V mainfont="Segoe UI" -V mainfontfallback="Segoe UI Emoji:mode=harf" -o worksheet.pdf worksheet.md
	@echo Build success.
