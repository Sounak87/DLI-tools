#! /bin/sh

# dli-multi
# =================
# A convenience wrapper to the dli script for batch processing a list of books to download.
#
# USAGE: dli-multi <filename>
#        <filename> - file in which each line contains (only) a DLI barcode and local ad-hoc book name separated by whitespace

[ "$#" != "1" ] && echo "USAGE: dli-multi <filename>" >&2 && exit 1

cat "$1" | while read barcode bookname
do
	echo $barcode $bookname
	if [ -z "$barcode" -o -z "$bookname" ] ; then
		echo "ERROR: malformed input line: $barcode $bookname"
		continue
	fi
	pdffilename=$(echo $bookname|tr " " "_")
	dli "$barcode" --pdf-name="$pdffilename"
done
