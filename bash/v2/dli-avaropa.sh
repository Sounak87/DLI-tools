#! /bin/bash

# dli-avaropa
# ===========
# A simple command-line utility for downloading books from the DLI and combining them to PDFs
# NOTE: Use it for good things.
#
# (c) Shriramana Sharma, 2015, samjnaa-at-gmail-dot-com
# Licensed for free use under the GPLv2+. NO WARRANTY.
#
# DEPENDENCIES: aria2 package (for aria2c) and libtiff-tools packages (for
# tiffcp and tiff2pdf) on Ubuntu; the parallel packages on other Linux distros.
# I don't know and can't help about other platforms, sorry.
#
# USAGE: dli-avaropa <barcode> <bookname>
#        <barcode>  - bar code of required DLI scan to download
#        <bookname> - book name to save files under; a temporary work directory will be created using this as well

function message { echo "*** dli-avaropa: $1" ; }
function errorAndExit { echo "*** dli-avaropa ERROR: $1" >&2 ; exit 1 ; }
function alreadyExistsContinue { message "$1 already exists; assuming this is from an earlier attempt to download" ; }

[ "$#" != "2" ] && errorAndExit "USAGE: dli-avaropa <barcode> <bookname>"
BOOKNAME="$2"

[ -f books/"$BOOKNAME".pdf ] && errorAndExit "The PDF of this book \"$BOOKNAME\" already seems to exist"
[ -f tifs/"$BOOKNAME".zip ] && errorAndExit "TIFs for this book \"$BOOKNAME\" already seem to exist"
# not checking if barcode exists since the barcode alone is of no use

# CHECKING AND ENTERING WORK DIRECTORY

WORKDIR="~/dli/$2"

if [ -d "$WORKDIR" ] ; then
	alreadyExistsContinue "Work directory $WORKDIR"
else
	mkdir -p "$WORKDIR" || errorAndExit "Could not create work directory $WORKDIR"
fi

if cd "$WORKDIR" ; then
	message "Entering work directory $WORKDIR"
else
	errorAndExit "Could not enter work directory $WORKDIR"
fi

if [ -f barcode.txt ] ; then
	[ "$(< barcode.txt)" = "$1" ] || errorAndExit "File barcode.txt exists but does not contain current barcode; exiting to be safe"
else
	echo "$1" > barcode.txt
fi

# GETTING URLS OF TIFS

if [ -f urls.txt ] ; then
	alreadyExistsContinue "File urls.txt"
else
	if [ -f allmetainfo.cgi ] ; then
		alreadyExistsContinue "File allmetainfo.cgi"
	else
		if ! aria2c -c "http://www.dli.ernet.in/cgi-bin/DBscripts/allmetainfo.cgi?barcode=$1" ; then
			cd ..
			rmdir "$WORKDIR"
			errorAndExit "Could not access the metadata page. Perhaps the barcode number is wrong or the network is not reachable"
		fi
	fi
	VIEWURL="$(echo $(grep -A1 FullindexDefault allmetainfo.cgi) | cut -d '"' -f10)" # echo $() needed to join two output lines of grep into one to complete URL
	# http://www.new.dli.ernet.in/scripts/FullindexDefault.htm?path1=/rawdataupload/upload/0121/707 &first=1&last=530&barcode=5990010121705
	# http://www.new1.dli.ernet.in/scripts/FullindexDefault.htm?path1=/data9/upload/0291/884&first=1&last=217&barcode=99999990293952
	SERVER="$(echo "$VIEWURL" | cut -d '/' -f-3)"
	# http://www.new.dli.ernet.in
	# http://www.new1.dli.ernet.in
	PATHSPEC="$(echo "$VIEWURL" | cut -d '=' -f2-4 | cut -d '&' -f-3)"
	# /rawdataupload/upload/0121/707 &first=1&last=530
	# /data9/upload/0291/884&first=1&last=217
	SUBDIR="$(echo "$PATHSPEC" | cut -d ' ' -f1 | cut -d '&' -f1)"
	# /rawdataupload/upload/0121/707
	# /data9/upload/0291/884
	STARTPAGE="$(echo "$PATHSPEC" | cut -d '=' -f2 | cut -d '&' -f1)"
	# 1
	# 1
	ENDPAGE="$(echo "$PATHSPEC" | cut -d '=' -f3)"
	# 530
	# 217
	for (( p = STARTPAGE ; p <= ENDPAGE ; ++p )) ; do
		printf "${SERVER}${SUBDIR}/PTIFF/%08d.tif\n" $p
	done > urls.txt && message "URLs printed to urls.txt; starting download" && rm allmetainfo.cgi
fi

# DOWNLOADING TIFS

if aria2c -c -i urls.txt ; then
	message "TIFFs downloaded; now converting to PDF"
	rm urls.txt
else
	# The DLI CGI script sometimes seems to return a wrong value for the last page 
	# which is one more than the true number of pages to download. Since this happens
	# often, we assume that if only the last page is not available, then it is because
	# of this error on part of the CGI script and so we proceed to convert to PDF.
	# Note that aria2c returns exit status 3 for "resource not available".
	# If any other error, of course we should abort.
	
	[ $? = 3 ] || errorAndExit "aria2c exited with status $?; not proceeding with TIFF to PDF conversion" 
	
	STARTPAGE="$(basename $(head -n1 urls.txt) ".tif")"
	ENDPAGE="$(basename $(tail -n1 urls.txt) ".tif")"
	SUCCESS=1
	for (( p = $(( 10#$STARTPAGE )) ; p < $(( 10#$ENDPAGE )) ; ++p )) ; do
		if [ ! -f $(printf "%08d.tif" $p) ] ; then
			SUCCESS=0
			break
		fi
	done
	if (( $SUCCESS )) ; then
		rm urls.txt
	else
		errorAndExit "Some page(s) could not be downloaded; not proceeding with TIFF to PDF conversion"
	fi
fi

# POSTPROCESSING AND CLEANING UP

if tiffcp *.tif temp.tif && tiff2pdf temp.tif -o output.pdf ; then
	rm temp.tif
	message "Output PDF book created"
	
	if zip -q tifs.zip $(ls *.tif) ; then
		rm *.tif
		message "TIFs backed up to ZIP file"
	fi
	
	while read SRCFILE EXT TGTDIR ; do
		TGTFILE="$BOOKNAME.$EXT"
		TGTPATH="../../$TGTDIR/$TGTFILE"
		if [ -f "$TGTPATH" ] ; then
			errorAndExit "File $TGTFILE has suddenly appeared in directory $TGTDIR/; this should not happen!"
		else
			mv "$SRCFILE.$EXT" "$TGTPATH" && message "File $TGTFILE moved to directory $TGTDIR/"
		fi
	done <<- EOF
		barcode txt barcodes
		output pdf books
		tifs zip tifs
	EOF
	
fi

cd ../..
rmdir --ignore-fail-on-non-empty -p "$WORKDIR" # remove the work directory if it is empty
