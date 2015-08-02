#! /bin/sh

# dli-avaropa-multi
# =================
# A convenience wrapper to the dli-avaropa script for batch processing a list of books to download
#
# (c) Shriramana Sharma, 2015, samjnaa-at-gmail-dot-com
# Licensed for free use under the GPLv2+. NO WARRANTY.
#
# USAGE: dli-avaropa-multi <filename>
#        <filename> - file in which each line contains (only) a DLI barcode and local ad-hoc book name separated by whitespace
set -o verbose
[ "$#" != "1" ] && echo "USAGE: dli-avaropa-multi.sh <filename>" >&2 && exit 1

cat "$1" | while read barcode bookname
do
	if [ -z "$barcode" -o -z "$bookname" ] ; then
		echo "dli-avaropa-multi.sh ERROR: malformed input line: $barcode $bookname"
		continue
	fi
	~/DLI-tools/bash/v2/dli-avaropa-multi.sh "$barcode" $bookname
done
