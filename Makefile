LATEXMK  = latexmk
PDFLATEX = pdflatex
SRCDIR   = src
OUTDIR   = output
MAIN     = $(SRCDIR)/main.tex

.PHONY: all clean watch

all:
	$(LATEXMK) -pdf -pdflatex="$(PDFLATEX) -interaction=nonstopmode -halt-on-error" \
	  -outdir=../$(OUTDIR) -cd $(MAIN)

clean:
	$(LATEXMK) -C -outdir=../$(OUTDIR) -cd $(MAIN)
	rm -f $(OUTDIR)/*.pdf

watch:
	$(LATEXMK) -pdf -pvc -pdflatex="$(PDFLATEX) -interaction=nonstopmode" \
	  -outdir=../$(OUTDIR) -cd $(MAIN)
