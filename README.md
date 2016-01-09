Scripts for use with the Digital Library of India (DLI) website. 
[https://sites.google.com/site/sanskritcode/]. Contributions welcome!

Vishvas likes the Bash tool best.

dli downloader (mac osx / linux)

=Other tools
==Aupasana tool
[https://raw.githubusercontent.com/aupasana/aupasana/master/OSXScripts/dli.py] dli.py - a python script to search for Digital Library of India books by barcode (on multiple mirrors), download the tiff files from a specific server, and then convert and combine them into a single pdf.

Please ensure the following tools are installed and available in the default path: wget, tiffcp and tiff2pdf
The simplest way to use the script is to specify the barcode alone. It will contact the default DLI server to create a file named barcode.pdf.
python dli.py --barcode BARCODE
Here's a more detailed workflow --
Lookup which servers have a copy of this book
python dli.py --lookup --barcode BARCODE
Download the individual pages from the specified server
python dli.py --download --barcode BARCODE --server SERVER
Create a pdf from these files
python dli.py --create-pdf --barcode BARCODE --pdf-file bookname.pdf
This tool supports multiple methods to create a pdf from the DLI files:
--pdf-tool tiff2pdf ... this is the default and uses tiffcp and tiff2pdf
--pdf-tool gs ... use imagemagick to convert tiffs to pdfs and then gs to combine  them into a single file. This is slower than the previous method, but file sizes are comparable.
--pdf-tool sips ... use the built in macos sips and automator to convert tiffs to pdfs and then combine them into a single file (mac OSX only). This is a quick process, but the resulting file sizes are huge (5 times the original file sizes)
This tool supports downloading files with both curl and wget. It runs multiple instances of these tools to download files in parallel. wget output works better and is the default. You can use curl if you must.