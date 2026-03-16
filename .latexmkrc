$pdf_mode = 1;
$pdflatex = 'pdflatex -interaction=nonstopmode -halt-on-error %O %S';
# Do NOT set $out_dir here - Makefile passes -outdir
$bibtex_use = 0;
