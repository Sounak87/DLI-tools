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
# USAGE: dli-avaropa <barcode> <parentdir>
#        <barcode>   - bar code of required DLI scan to download
#        <parentdir> - directory under which new directory will be created for downloading
#                      the TIFs and assembling them
#
# KNOWN LIMITATION:
# The DLI CGI script sometimes seems to return a wrong value for the last page 
# which is one more than the true number of pages to download. This script cannot 
# be expected to divine this error of the server. So the only go is to manually 
# run the command used at the end of the download process to create the PDF:
#   tiffcp *.tif temp.tif && tiff2pdf temp.tif -o output.pdf && rm temp.tif
# You may backup/delete the rest of the downloaded TIFs as you wish.
if [ "$#" != "2" ] ; then echo "USAGE: dli-avaropa <barcode> <parentdir>" >&2 ; exit 1 ; fi
TARGETDIR="$2/dli-avaropa-$1"
if [ ! -d "$TARGETDIR" ] ; then
if ! mkdir "$TARGETDIR" ; then echo "*** dli-avaropa: Could not create target directory $TARGETDIR" >&2 ; exit 1 ; fi
else
echo "*** dli-avaropa: target directory $TARGETDIR already exists; assuming this is from an earlier attempt to download"
fi
if ! cd "$TARGETDIR" ; then
echo "*** dli-avaropa: could not enter target directory $TARGETDIR" >&2
exit 1
fi
if [ -f output.pdf ] ; then
echo "*** dli-avaropa: output.pdf already exists; assuming this is from a completed download and exiting"
exit
fi
if [ -f urls.txt ] ; then
echo "*** dli-avaropa: urls.txt already exists; assuming this is from an incomplete download and continuing"
else
if [ -f allmetainfo.cgi ] ; then
echo "*** dli-avaropa: allmetainfo.cgi already exists; assuming this is from an incomplete download and continuing"
else
if ! aria2c -c "http://www.dli.ernet.in/cgi-bin/DBscripts/allmetainfo.cgi?barcode=$1" ; then
echo "*** dli-avaropa: Could not access the metadata page. Perhaps the barcode number is wrong or the network is not reachable" >&2
rmdir "$TARGETDIR"
exit 1
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
for (( p = STARTPAGE ; p <= ENDPAGE ; ++p )) ; do printf "${SERVER}${SUBDIR}/PTIFF/%08d.tif\n" $p ; done > urls.txt && echo "*** dli-avaropa: URLs printed to urls.txt; starting download" && rm allmetainfo.cgi
fi
if aria2c -c -i urls.txt ; then
echo "*** dli-avaropa: TIFFs downloaded; now converting to PDF"
rm urls.txt
else
echo "*** dli-avaropa: aria2c exited with status $?; not proceeding with TIFF to PDF conversion" >&2
exit $?
fi
tiffcp *.tif temp.tif && tiff2pdf temp.tif -o output.pdf && {
echo "*** dli-avaropa: output.pdf created under $TARGETDIR"
rm temp.tif
mkdir tifs && mv *.tif tifs/ && echo "*** dli-avaropa: TIFs backed up to tifs directory"
}
cd ..
