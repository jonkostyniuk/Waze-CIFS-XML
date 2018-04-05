# ##########################################################################################################
# WAZE CLOSURE AND INCIDENT FEED SPECIFICATION (CIFS) XML GENERATOR
# Created by Jon Kostyniuk on 2018-04-04
# Last modified by Jon Kostyniuk on 2018-04-04
# Property of JK Enterprises
# v1.0.0b
# ##########################################################################################################
#
# Version History:
# ----------------
# 2018-04-04 v1.0.0b - JDK
#   - Initial Version.
#
# Usage:
# ------
# Used to generate a CIFS XML file for intake by Waze's Connected Citizens Program (CCP).
#
# Instructions:
# -------------
# Call script to query active database records and subsequently generate CIFS XML file.
#

# ##########################################################################################################
# MODULES AND DEFINITIONS
# ##########################################################################################################

# STANDARD MODULES
# ----------------

from shutil import copyfile, copy2
import commands
import dicttoxml as dxml
import signal
import time

# CUSTOM MODULES
# --------------

import db_access as dba

# GLOBAL VARIABLE DEFINITIONS
# ---------------------------

# File and Directory Names
dirSource = "./" # Source Directory
dirDest = "./public_html/" # Destination Directory
fCIFSxml = "traffic-incidents.xml" # File Name for Output CIFS XML
fCIFSschema = "incidents_feed-2.0.0.mod.xsd" # CIFS XML Schema File

# Validation Tools
XMLschema = "https://www.gstatic.com/road-incidents/incidents_feed.xsd" # Google-side XML Schema Verification

# Control Variables
secTimeout = 30 # Program Function Timeout (seconds)


# ##########################################################################################################
# MAIN PROGRAM
# ##########################################################################################################

# Function to Handle Main Program
def main():
	# Update Incidents from Database
	signal.signal(signal.SIGALRM, timeout) # Register the signal function handler
	signal.alarm(secTimeout) # Set Timeout Duration
	try:
		dIncidents = dba.update()
		#loop_forever() # TEST CALL
	except Exception, exc: 
		dba.msg_log(time.time(), str(exc)) # Log exception message
		return
	signal.alarm(0) # Cancel timeout upon success

	# Generate CIFS XML File
	try:
		generate_cifs_xml(dIncidents)
	except:
		dba.msg_log(time.time(), "ERROR: CIFS XML file failed to generate!!")

	# Validate CIFS XML Against Local Schema
	chkSchema = commands.getoutput('xmllint --schema ' + fCIFSschema + ' --noout ' + fCIFSxml)
	if chkSchema != fCIFSxml + " validates":
		dba.msg_log(dIncidents["timestamp"], "ERROR: CIFS XML file did not validate against schema!!")
		return

	# Link CIFS XML File to Public Folder
	### Waze ideally recommends a symbolic link, but using direct copy given small file size.
	copy2((dirSource + fCIFSxml), (dirDest + fCIFSxml)) # Copy file path from source to destination

	# Record Success Message in Log File
	dba.msg_log(time.time(), "SUCCESS: Updated CIFS XML file generated!!")

	return


# ##########################################################################################################
# DEFINED FUNCTIONS
# ##########################################################################################################

# MODULE FUNCTIONS
# ----------------

# Function to Generate CIFS XML File
def generate_cifs_xml(dIncidents):
	# Initialize CIFS XML Headers
	init_xml(dIncidents["timestamp"])
	# Construct CIFS XML Records
	for incident in dIncidents["incident"]:
		xmltxt = '  <incident id="' + str(incident["id"]) + '">\n'
		xmltxt += '    <creationtime>' + incident["creationtime"] + '</creationtime>\n'
		xmltxt += '    <updatetime>' + incident["updatetime"] + '</updatetime>\n'
		xmltxt += '    <source>\n'
		xmltxt += '      <reference>' + incident["source"]["reference"] + '</reference>\n'
		xmltxt += '      <name>' + incident["source"]["name"] + '</name>\n'
		xmltxt += '      <url>' + incident["source"]["url"] + '</url>\n'
		xmltxt += '    </source>\n'
		xmltxt += '    <type>' + incident["type"] + '</type>\n'
		xmltxt += '    <description>' + incident["short_description"] + '</description>\n' # USING SHORT DESCRIPTION DUE TO VALIDATION ERROR
		xmltxt += '    <location>\n'
		xmltxt += '      <street>' + incident["location"]["street"] + '</street>\n'
		xmltxt += '      <polyline>' + incident["location"]["polyline"] + '</polyline>\n'
		xmltxt += '      <direction>' + incident["location"]["direction"] + '</direction>\n'
		xmltxt += '    </location>\n'
		xmltxt += '    <starttime>' + incident["starttime"] + '</starttime>\n'
		xmltxt += '    <endtime>' + incident["endtime"] + '</endtime>\n'
		#xmltxt += '    <short_description>' + incident["short_description"] + '</short_description>\n'
		xmltxt += '  </incident>\n'
		with open(fCIFSxml, "a") as fh:
			fh.write(xmltxt)
	# Finalize CIFS XML Footers
	finalize_xml()
	return

# HELPER (MONKEY) FUNCTIONS
# -------------------------

# Function to Finalize CIFS XML File
def finalize_xml():
	xmltxt = '</incidents>\n'
	with open(fCIFSxml, "a") as fh:
		fh.write(xmltxt)
	return

# Function to Initialize CIFS XML File
def init_xml(timestamp):
	xmltxt = '<?xml version="1.0" encoding="UTF-8"?>\n'
	xmltxt += '<incidents xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
	xmltxt += 'xsi:noNamespaceSchemaLocation="' + XMLschema
	xmltxt += '" timestamp="' + timestamp + '">\n'
	with open(fCIFSxml, "w") as fh:
		fh.write(xmltxt)
	return

# Function to Loop Forever [TESTING ONLY]
def loop_forever():
	while 1:
		print "sec"
		time.sleep(1)
	return

# Function to Timeout Data Request
def timeout(signum, frame):
	raise Exception("ERROR: Data update request has timed out!!")
	return

# NAMESPACE CALL (DO NOT MODIFY)
# ------------------------------
if __name__ == "__main__":
	main()


# ##########################################################################################################
# END OF SCRIPT
# ##########################################################################################################