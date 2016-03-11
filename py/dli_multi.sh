#! /bin/sh

# dli-multi
# =================
# A convenience wrapper to the dli-avaropa script for batch processing a list of books to download. Based on a similar scipt by shrIramaNa.
#
# USAGE: dli-multi <filename>
#        <filename> - file in which each line contains (only) a DLI barcode and local ad-hoc book name separated by whitespace
# set -o verbose

[ "$#" != "1" ] && echo "USAGE: dli-multi.sh <filename>" >&2 && exit 1

cat "$1" | while read barcode bookname
do
	echo $barcode $bookname
	if [ -z "$barcode" -o -z "$bookname" ] ; then
		echo "dli-avaropa-multi.sh ERROR: malformed input line: $barcode $bookname"
		continue
	fi
	~/DLI-tools/py/dli.py "$barcode" --pdf-name="\"$bookname\""
done
