#!/usr/bin/env python
# INVOCATION: dli.py BARCODE
"""
dli.py has the logic to chase the references on every single server and to find one that actually hosts the images. Once the images are downloaded, it also deals with some malformed tiff images that libtiff has trouble with. The servers are also ordered by the fastest most available ones (based on my experience).

My suggestion is to use dli.py unless you have a specific need to use the other downloaders ... it has logic to deal with all the edge cases I've run into.

I use the following one liner to download multiple books

        cat barcodes.txt | xargs -n1 ./dli.py

And I watch detailed progress by tailing the log file

        tail -f dli.py.log
"""
import sys

# Require python version 2.[7+]
major = sys.version_info[0]
minor = sys.version_info[1]
if (major != 2 or minor < 7):
	print("This script requires python version 2.7 or higher (2.x)")
	sys.exit()

# Put import in a try block to get a simple error message
# if the import isn't found
try:
	import argparse
	import glob
	import linecache
	import logging
	import os
	import pipes
	import re
	import shutil
	import subprocess
	import time
	import urllib2
	from urlparse import urlparse, parse_qs
except ImportError as exception:
	print "Unable to find python module: {}".format(exception)
	sys.exit()

lxmlpresent = False

try:
	from lxml import html
	lxmlpresent = True
except:
	pass


# global parameters
# parser is global to call print_help from anywhere
args = None
parser = None
FNULL = open(os.devnull, 'w')

# prioritized list of known DLI servers
servers = [
	'202.41.82.144',
	'www.dli.ernet.in',
	'www.new.dli.ernet.in',
	'www.dli.gov.in',
	'www.new.dli.gov.in',
	'www.new1.dli.ernet.in'  # at the end of the list since the page counts don't currently work
]

def main(argv):

	# Preamble
	# Note: Argument parsing is split into two parts
	# so that we can initialize the logger as early as possible
	# based on the value of --log-file
	parsearguments()
	initializelogging()

	logging.debug("")
	logging.debug("##############")
	logging.debug("Logging initialized")
	logging.debug("##############")
	logging.debug("")
	logging.debug("Running python version {} on {}".format(sys.version_info, sys.platform))

	validatearguments()

	# note: since it doesn't make sense to combine --list-servers/--lookup
	# with --download/--createpdf, exit after those operations are complete

	# --no-check_tools
	if (args.no_check_tools == False):
		checktools()

	# --list-servers
	if (args.list_servers == True):
		listservers()
		sys.exit()

	# --lookup
	# reset args.servers based on the lookup call
	if (args.lookup == True):
		goodserver = lookup()

	# --download
	if (args.download == True):
		if (args.lookup == False):
			goodserver = lookuponserver(args.server[0])

		if (goodserver == None):
			logging.info("Cannot download since no server was found")
			sys.exit(-1)

		server, url, pages, firstpagedownloaded = goodserver
		downloadbook(server, url, pages)

	# --create-pdf
	if (args.create_pdf == True):
		createpdf()
		logging.info ("PDF Creation complete")

	if (args.resize_pdf == True):
		resizepdf()

	# After pdf operations, open the pdf if requested
	if (args.create_pdf == True or args.resize_pdf == True):
		platform = sys.platform

		logging.debug ("Opening file {}".format(args.pdf_name))
		if (platform == 'darwin'):
			cmd = "open {}".format(pipes.quote(args.pdf_name))
			os.system(cmd)
		elif (platform == 'win32'):
			os.startfile(args.pdf_name)

def parsearguments():
	global args
	global parser

	parser = argparse.ArgumentParser(description='Download books from the Digital Library of India (DLI)')

	# actions
	parser.add_argument('--list-servers', action='store_true', help='list known DLI servers')
	parser.add_argument('--lookup', action='store_true', help='lookup the book with the specified [BARCODE] on all [SERVER]')
	parser.add_argument('--download', action='store_true', help='download the book with the specified [BARCODE] from the first [SERVER]')
	parser.add_argument('--create-pdf', action='store_true', help='create a pdf from the downloaded files')
	parser.add_argument('--resize-pdf', action='store_true', help='set pdf page size to the value specified in --pdf-size')

	parser.add_argument('barcode', type=int, nargs='?', help='specify the barcode for the book')
	parser.add_argument('--barcode', type=int, nargs='?', dest='barcode2', help='specify the barcode for the book (for backwards compatibility)')

	parser.add_argument('--server', default=servers, nargs='*', help='see --list for known servers (default: 202.41.82.144)')
	parser.add_argument('--first', default='1', type=int, help='first page to --download')
	parser.add_argument('--last', nargs='?', type=int, help='last page to --download')
	parser.add_argument('--timeout', default='120', type=int, help='seconds to wait for DLI servers to respond during --download (default: 120)')
	parser.add_argument('--lookup-timeout', default='10', type=int, help='seconds to wait for DLI servers to respond during --lookup (default: 10)')
	parser.add_argument('--download-parallel', dest='threads', default='5', type=int, help='number of parallel operations during --download (default: 5)')
	parser.add_argument('--pdf-name', nargs='?', help='specify the output pdf file name (default [BARCODE].pdf)')
	parser.add_argument('--directory', nargs='?', help='the directory in which downloaded files are stored (default [BARCODE])')
	parser.add_argument('--overwrite', action='store_true', help='overwrite existing local files')
	parser.add_argument('--download-tool', default='wget', help='tool used to download files: aria|wget|curl (default: wget)')
	parser.add_argument('--pdf-tool', default='tiff2pdf', help='tool chain used to generate pdf file: gs|sips|tiff2pdf (default: tiff2pdf)')
	parser.add_argument('--pdf-size', default='letter', help='pdf paper size: a4|letter (default: letter)')
	parser.add_argument('--pdf-open', action='store_true', help='open pdf after creation (osx only)')
	parser.add_argument('--log-file', default='dli.py.log', help='log file location: filename|NUL|/dev/null (default: dli.py.log)')
	parser.add_argument('--no-check-tools', action='store_true', help='check to see if tools are installed properly')
	parser.add_argument('--no-title-in-pdf-name', action='store_true', help='do not default to the title for the pdf name')
	parser.add_argument('--no-delete-temp', action='store_true', help='do not delete temporary files after pdf creation')

	args = parser.parse_args()

def validatearguments():
	global args
 	global parser

 	# backward compatibility --barcode was a named parameter and is now a positional parameter
 	if(args.barcode2 != None):
 		if(args.barcode == None):
 			args.barcode = args.barcode2
 		else:
 			logging.error("Cannot specify both [barcode] and --barcode2")
 			sys.exit()

	# If no action is specified, show help
	# Special case: If the barcode is specified, automatically infer --lookup --download --create-pdf for ease of user
	if(args.list_servers == False
		and args.lookup == False
		and args.download == False
		and args.create_pdf == False
		and args.resize_pdf == False
	):
		if (args.barcode != None):
			args.lookup = True
			args.download = True
			args.create_pdf = True
		else:
			parser.print_help()
			sys.exit()

	# Ensure barcode is specified when required
	if(args.lookup == True or args.download == True):
		if (args.barcode == None):
			logging.error("Error: A barcode must be specified")
			sys.exit()

	# If the directory isn't specific, it defaults to the barcode
	if (args.directory == None and args.barcode != None):
		args.directory = str(args.barcode)

	# Ensure the directory doesn't contain spaces
	if (args.directory != None and (' ' in args.directory) == True):
		logging.error("Error: the --directory cannot contain spaces")
		sys.exit()

	# If --pdf-name is specified, don't overwrite with title
	if (args.pdf_name != None):
		args.no_title_in_pdf_name = True

	# If --pdf-name is not specified, it defaults to barcode.pdf
	if (args.pdf_name == None and args.barcode != None):
		args.pdf_name = "{}.pdf".format(args.barcode)

	# Ensure --pdf-name doesn't contain spaces
	if (args.pdf_name != None and (' ' in args.pdf_name) == True):
		logging.error("Error: the --pdf-name cannot contain spaces")
		sys.exit()

	# validate --download-tool
	if (not args.download_tool in ['wget', 'curl', 'aria']):
		logging.error("Error: unknown value specified for --download-tool")
		sys.exit()

	# validate --pdf-tool
	if (not args.pdf_tool in ['gs', 'sips', 'tiff2pdf']):
		logging.error("Error: unknown value specified for --pdf-tool")
		sys.exit()

	# --pdf-tool sips is only supported on osx
	if (args.pdf_tool == 'sips' and sys.platform != 'darwin'):
		logging.error("Error: --pdf-tool sips is only supported on mac osx")
		sys.exit()

	if (args.resize_pdf == True and args.pdf_name == ''):
		logging.error("Cannot --resize-pdf when no --pdf-name is specified")
		sys.exit()

	logging.debug ("arguments {}".format(args))


def checktools():

	logging.debug("Entering checktools()")

	tools = []

	if (args.download == True):
		if(args.download_tool == 'aria'):
			tools.append('aria2c')
		elif (args.download_tool == 'wget'):
			tools.append('wget')
			tools.append('xargs')
		elif (args.download_tool == 'curl'):
			tools.append('curl')
			tools.append('xargs')

	if (args.create_pdf == True):
		# note: sips has no dependencies
		if (args.pdf_tool == 'tiff2pdf'):
			tools.append('tiffcp')
			tools.append('tiff2pdf')
		elif (args.pdf_tool == 'gs'):
			tools.append('mogrify')
			tools.append('gs')

	if (args.resize_pdf == True):
		tools.append('gs')

	# only need to check for each tool once
	toolset = set(tools)

	# print list(set) for readability
	logging.debug("Checking for the following required tools: {0}".format(list(toolset)))

	toolsnotfound = []
	for i, tool in enumerate(toolset):
		toolpresent = False
		logging.debug("Checking to see if {0} is present".format(tool))
		try:
			subprocess.call([tool, "-h"], stdout=FNULL, stderr=FNULL)
			toolpresent = True
		except OSError as exception:
			if exception.errno == os.errno.ENOENT:
				logging.debug("OSError")
				printexception(exception)
		except Exception as exception:
			logging.debug("Non-OSError Exception")
			printexception(exception)

		logging.debug("Is {0} present: {1}".format(tool, toolpresent))
		if (toolpresent == False):
			toolsnotfound.append(tool)

	if (len(toolsnotfound) > 0):
		logging.error("The following tools are required to run this command: {0}".format(toolsnotfound))
		logging.error("Please install/configure them and try again")
		sys.exit(-1)

	if (lxmlpresent == False):
		logging.warning("Warning: The lxml python module is not present. Run 'pip install lxml' to install it")


def listservers():
	logging.info ("Servers:")
	logging.info ("-------")
	for i, al in enumerate(servers):
		logging.info (servers[i])


def lookup():
	logging.debug("Enter lookup()")

	goodserver = None
	allgoodservers = []

	for i, server in enumerate(args.server):
		logging.debug("Lookup up {0}".format(server))
		try:
			ret = lookuponserver(server)
			server, url, pages, firstpagedownloaded = ret
			logging.debug("Result of lookup: {}".format(ret))

			if (firstpagedownloaded == True):
				allgoodservers.append(server)

			if (firstpagedownloaded == True and goodserver == None):
				goodserver = ret

			logging.debug("Allgoodservers: {}".format(allgoodservers))

			# If we have found a "good" server, and this command is chained
			# with --download, we are simply going to use the first good server,
			# so there is no point interrogating the remainder of the servers
			if (args.download == True):
				logging.debug("Found one good server and --download was specified. Bailing out of lookup() early.")
				break
		except Exception as exception:
			printexception(exception)
			pass

	if (args.download != True):
		logging.info ("Servers that host this book are: {}".format(allgoodservers))

	return goodserver

def getbookproperty(tree, key):
	logging.debug("Looking up book property {0}".format(key))
	value = None

	#  <tr>
	#    <td bgcolor="#DDDDDD"><div align="center"><strong><font face="Arial size="2", Helvetica, sans-serif">Author1</font></strong></div></td>
	#    <td bgcolor="#E8EEF7"><div align="center"><font face="Arial  size="2", Helvetica, sans-serif">111</font></div></td>
	#  </tr>
	#
	# The properties are in snippets like the one above
	# Look for the key in text wrapped by font, and walk up 4 levels to tr (strong, div, td, tr)
	# Then walk down from tr to td/div/font, and return the value in that node

	try:
		format = "//*/font[text()='{}']/../../../../td/div/font[text()]".format(key)
		node = tree.xpath(format)
		value = node[0].text
	except:
		logging.debug("Error obtain value of key {0}".format(key))

	logging.debug("Value of property {0} is {1}".format(key, value))

	key = key.strip()
	if (value != None):
		value = value.strip()

	if (value == ''):
		value = None

	return (key, value)


def getbookproperties(htmlstring):
	logging.debug("getbookproperties::enter")
	if (lxmlpresent == False):
		return None

	logging.debug("getting book properties")
	tree = html.fromstring(htmlstring)

	properties = []
	try:
		node = tree.xpath("//*/tr/td/div/strong/font")

		for i, n in enumerate(node):
			properties.append(n.text)
	except:
		logging.debug("Error enumerating keys")

	# properties = ["Title", "Author1", "Subject", "Language", "Barcode", "Year", "Year "]
	values = []
	for i, key in enumerate(properties):
		value = getbookproperty(tree, key)
		k, v = value
		if (v != None):
			values.append(value)

	return values


def lookuponserver(server):
 	logging.info ("Looking up book {} on {}".format(args.barcode, server))

	try:
		infourl = 'http://' + server + '/cgi-bin/DBscripts/allmetainfo.cgi?barcode=' + str(args.barcode)

		logging.debug("downloading {} with a timeout of {} seconds".format(infourl, args.lookup_timeout))

		start = time.time()
		htmlresponse = urllib2.urlopen(infourl, timeout=args.lookup_timeout)
		rawhtml = htmlresponse.read()
		end = time.time()

		html = re.sub('\n', '', rawhtml)

		# The raw html is too verbose even for --debug. Uncomment when necessary
		# logging.info (rawhtml)

		properties = getbookproperties(rawhtml)

		# Find first link after 'Read Online'
		match = re.search('Read Online.*<a href="([^"]*)', html)
		readurl = match.group(1)

		logging.debug('url is {}'.format(readurl))

		parsedurl = urlparse(readurl)
		parsedquery = parse_qs(parsedurl.query)

		# If URL is relative, it's relative to the server we queried
		netloc = parsedurl.netloc
		if netloc == '':
			netloc = server

		# If path is not specified as a query parameter, it's the entire URL
		if 'path1' in parsedquery:
			path = parsedquery['path1'][0]
		else:
			path = readurl

		url = 'http://' + netloc + path;

		pages = '?'
		if 'last' in parsedquery:
			pages = parsedquery['last'][0]

		logging.info ('server [%s] shows %s pages at %s in %f seconds' % (server, pages, url, end-start))

		if (properties != None and len(properties) > 0):
			propertiesdict = dict(properties)
			if (args.no_title_in_pdf_name != True):
				args.pdf_name = "{0}_{1}.pdf".format(propertiesdict["Title"].replace(' ', '_'), args.barcode)
				logging.debug("Setting --pdf-name to {0}".format(args.pdf_name))
			pages = propertiesdict["TotalPages"]

			if "Title" in propertiesdict:
				logging.info('    Title: {0}'.format(propertiesdict["Title"]))
			if "Author1" in propertiesdict:
				logging.info('    Author: {0}'.format(propertiesdict["Author1"]))


		logging.debug ('book properties: {}'.format(properties))

		firstpageurl = "{0}/PTIFF/{1:08d}.tif".format(url, 1)
		firstpagedownloaded = False

		try:
			start = time.time()
			htmlresponse = urllib2.urlopen(firstpageurl, timeout=args.timeout)
			rawhtml = htmlresponse.read()
			end = time.time()
			firstpagedownloaded = True
			logging.info ("    page one downloaded successfully in {} seconds".format(end-start))
			return (server, url, pages, firstpagedownloaded)
		except urllib2.HTTPError, e:
			logging.warning("    Error {} downloading first page {}".format(e.code, firstpageurl))
		finally:
			pass


	except urllib2.HTTPError, e:
		logging.warning ("server [{}]: HTTPError ({}) performing lookup".format(server, e.code))
	except urllib2.URLError, e:
		logging.warning ("server [{}]: URLError ({}) performing lookup".format(server, e.reason))
	except Exception as exception:
		logging.warning ("server [{}]: Error performing lookup: {}" .format(server, exception.__class__.__name__))
		logging.debug(exception)
		printexception(exception)
	finally:
		logging.info ('')



def downloadbook(server, url, pages):

	logging.debug("downloading {} pages of book {} from {}".format(pages, args.barcode, url))

	if (args.last == None):
		args.last = pages

	logging.debug("downloading pages {} to {} with {} threads and a timeout of {} seconds to {}".format(args.first, args.last, args.threads, args.timeout, args.directory))

	if (args.last == '?'):
		logging.error("Error: Unable to determine the number of pages. Specify the --last argument explicitly")
		sys.exit()

	if (not os.path.exists(args.directory)):
		logging.debug("Creating directory {}".format(args.directory))
		os.makedirs(args.directory)
	else:
		logging.debug("Directory {} already exists. Skipping creation.".format(args.directory))

	logging.debug("Creating list of urls")

	allurls = ''
	for i in range(args.first, int(args.last) + 1):
		pageurl = "{0}/PTIFF/{1:08d}.tif".format(url, i)
		allurls = allurls + pageurl + '\n'

	urlfilename = "{0}/urls.txt".format(args.directory)

	with open(urlfilename, "wb") as filestream:
		filestream.write(allurls)

	logging.info ("Downloading files with {}".format(args.download_tool))

	if(args.download_tool == 'aria'):
		cmd = "aria2c -i urls.txt -x {0} --auto-file-renaming=false -l {1} >> ../{1} 2>> ../{1}".format(args.threads, args.log_file)
	elif (args.download_tool == 'wget'):
		if (sys.platform == 'win32'):
			# xargs -P doesn't seem to work on windows, so
			cmd = "wget -T {0} -i urls.txt -nc -nd --no-verbose >> ../{1} 2>> ../{1}".format(args.timeout, args.log_file)
		else:
			cmd = "cat urls.txt | xargs -n 1 -P {0} wget -T {1} -nc -nd --no-verbose >> ../{2} 2>> ../{2}".format(args.threads, args.timeout, args.log_file, args.log_file)
	elif (args.download_tool == 'curl'):
		cmd = "cat urls.txt | xargs -I % -n 1 -P {0} sh -c 'curl -sS -O % >> ../{1} 2>> ../{1}'".format(args.threads, args.log_file)

	logging.debug("cmd: {}".format(cmd))
	subprocess.call(cmd, shell=True, cwd=args.directory)

	tifCount = len(glob.glob1(args.directory, "*.tif"))
	logging.info ("Download script completed ... {} pages present in directory '{}'".format(tifCount, args.directory))


def createpdf():

	pdfdirectory = "{0}-temp-pdf".format(args.directory)

	if (not os.path.exists(pdfdirectory)) and (args.pdf_tool != 'tiff2pdf'):
		logging.debug("Creating temporary directory {}".format(pdfdirectory))
		os.makedirs(pdfdirectory)

	logging.info("Processing images with {} toolchain".format(args.pdf_tool))

	if (args.pdf_tool == 'tiff2pdf'):
		# stage0: extract the first page of multipage tif files with tiffcrop
		# stage1: combine all extracted tifs into one multi-page tiff
		# stage2: convert multi-page tiff to pdf

		cmd_stage0 = "ls *.tif | xargs -I % -n 1 -P 1 sh -c 'tiffcrop -N1 % crop_% >> ../{0} 2>> ../{0}'".format(args.log_file)
		cmd_stage1 = "tiffcp {0}/crop_*.tif {0}/combined.tif >> {1} 2>> {1}".format(args.directory, args.log_file)
		cmd_stage2 = "tiff2pdf -o {0} {1}/combined.tif >> {2} 2>> {2}".format(pipes.quote(args.pdf_name), args.directory, args.log_file)
	elif (args.pdf_tool == 'gs'):
		# grep stderr for "Load" to output a single line per file being processed
		# stage1: convert each page to pdf
		# stage2: combine pdf to multi-page pdf
		cmd_stage1 = "mogrify -monitor -format pdf -path {0}/ {1}/*.tif >> {2} 2>> {2}".format(pdfdirectory, args.directory, args.log_file)
		cmd_stage2 = "gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile={0} {1}/*.pdf >> {2} 2>> {2}".format(pipes.quote(args.pdf_name), pdfdirectory, args.log_file)
	elif (args.pdf_tool == 'sips'):
		# stage1: convert each page to pdf
		# stage2: combine pdf to multi-page pdf
		cmd_stage1 = "sips -s format pdf {0}/*.tif --out {1} >> {2} 2>> {2}".format(args.directory, pdfdirectory, args.log_file)
		cmd_stage2 = "/System/Library/Automator/Combine\ PDF\ Pages.action/Contents/Resources/join.py -o {0} {1}/*.pdf".format(pipes.quote(args.pdf_name), pdfdirectory)
	else:
		logging.error("Internal Error: Unknown value {} in args.pdf_tool".process(args.pdf_tool))
		sys.exit(-1)


	if (cmd_stage0 != None):
		logging.debug("Stage 0: {}".format(cmd_stage0))
		subprocess.call(cmd_stage0, shell=True, cwd=args.directory)

	logging.debug("Stage 1: {}".format(cmd_stage1))
	subprocess.call(cmd_stage1, shell=True)

	logging.debug("Stage 2: {}".format(cmd_stage2))
	subprocess.call(cmd_stage2, shell=True)

	pdfSize = os.path.getsize(args.pdf_name)

	logging.info("Created PDF file {} ({} bytes)".format(args.pdf_name, pdfSize))

	logging.info("")
	logging.info("Temporary TIFF download directory: '{}'".format(args.directory))
	if (os.path.exists(pdfdirectory)):
		logging.info("Temporary pdf directory: '{}'".format(pdfdirectory))

	if (args.no_delete_temp == False):
		logging.info("Deleting temporary files")

		shutil.rmtree(args.directory)
		if (os.path.exists(pdfdirectory)):
			shutil.rmtree(pdfdirectory)


def resizepdf():
	logging.debug ("Setting pdf page size to {}".format(args.pdf_size))

	resizedfilename = "{}_{}".format(args.pdf_size, args.pdf_name)

	cmd = "gs -o {0} -sDEVICE=pdfwrite -sPAPERSIZE={1} -dFIXEDMEDIA -dPDFFitPage {2} >> {3} 2>> {3}".format(pipes.quote(resizedfilename), args.pdf_size, pipes.quote(args.pdf_name), args.log_file)

	logging.debug ("Resizing: {}".format(cmd))
	logging.info("Resizing pdf")
	subprocess.call(cmd, shell=True)

	pdfSize = os.path.getsize(args.pdf_name)
	resizedSize = os.path.getsize(resizedfilename)

	logging.debug ("File {} ({} bytes) resized to {} ({} bytes)".format(pipes.quote(args.pdf_name), pdfSize, resizedfilename, resizedSize))

	if (os.path.exists(resizedfilename)):
		os.remove(args.pdf_name)
		os.rename(resizedfilename, args.pdf_name)
	else:
		logging.info ("resizing pdf failed. Please run the command manually to debug")

	logging.info ("Resize complete")


def initializelogging():
	# set up logging to file - see previous section for more details
	logging.basicConfig(level=logging.DEBUG,
		format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
		datefmt='%Y-%m-%d %H:%M',
		filename=args.log_file)
	#filemode='w')

	# define a Handler which writes INFO messages or higher to the sys.stderr
	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	# set a format which is simpler for console use
	formatter = logging.Formatter('%(message)s')
	# tell the handler to use this format
	console.setFormatter(formatter)
	# add the handler to the root logger
	logging.getLogger('').addHandler(console)


def printexception(exception):
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    logging.debug ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
    logging.debug ('{}'.format(exception.__class__.__name__))


if __name__ == "__main__":
	main(sys.argv[1:])
