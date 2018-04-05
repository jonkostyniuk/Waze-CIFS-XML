# ##########################################################################################################
# GIS CLOSURE AND INCIDENT FEED SPECIFICATION (CIFS) DATABASE ACCESS
# Created by Jon Kostyniuk on 2018-04-04
# Last modified by Jon Kostyniuk on 2018-04-04
# Property of JK Enterprises
# v0.1.0a
# ##########################################################################################################
#
# Version History:
# ----------------
# 2018-04-04 v1.0.0b - JDK
#   - Initial Version.
#
# Usage:
# ------
# Performs database query of CIFS data and converts to required data formats. You may choose whatever
# database backend required and supplement this script with supporting code. This script uses the test list
# object and data defined below. It can be repurposed for production use.
#
# This script module scrapes public Renew London data directly from the "https://apps.london.ca/RenewLondon"
# website and does not employ direct database access at this time.
#
# Instructions:
# -------------
# Imported externally in the same directory as 'waze_cifs_xml.py'.
#
# Reference:
# ----------
# http://jonathansoma.com/lede/algorithms-2017/servers/setting-up/
#

# ##########################################################################################################
# MODULES AND DEFINITIONS
# ##########################################################################################################

# STANDARD MODULES
# ----------------

from datetime import *
from pyvirtualdisplay import Display
from selenium import webdriver
import dateutil.parser as parser
import hashlib
import json
#import pandas as pd
import sqlite3 as sql
import time
import urllib3

# CUSTOM MODULES
# --------------

# n/a

# GLOBAL VARIABLE DEFINITIONS
# ---------------------------

# URL and API Source Data
urlRlmain = "https://apps.london.ca/RenewLondon" # Renew London Main URL
apiRLdisruptions = "https://apps.london.ca/RenewLondon/home/GetAllDisruptions" # JSON object of disruptions
apiJSobj = "return London.Renew.Public.Map.Services.ongoingData" # Access JavaScript Object

# SQLite Database Variables
sqlDBname = "renewlondon.db" # SQLite Database Name

# Control Variables
secSleep = 3 # Program Sleep Time (seconds)
curUnixTime = int(time.time()) # Get Current Unix Timestamp
fMsgLog = "./public_html/messages.html" # Message Log Text File

# Default Data Values
def_description = "Undisclosed work details" # Default Incident Description
def_short_description = "Caution workers present" # Default Incident Short Description


# ##########################################################################################################
# MAIN PROGRAM
# ##########################################################################################################

# Function to Handle Main Update Program
def update():
	# Scrape GIS Data from Public Website
	msg = "ERROR: GIS data scrape failed!!" # If error
	try:
		gisData = query_gis()
		if not gisData:
			print msg
			msg_log(curUnixTime, msg)
			return False
	except:
		print msg
		msg_log(curUnixTime, msg)
		return False
	
	# Query Disruptions Data from Public API
	msg = "ERROR: Disruption data API query failed!!" # If error
	try:
		apiData = query_details()
		if not apiData:
			print msg
			msg_log(curUnixTime, msg)
			return False
	except:
		print msg
		msg_log(curUnixTime, msg)
		return False

	# Parse Renew London Data into Python Dictionary
	msg = "ERROR: Data dictionary did not parse!!" # If error
	try:
		dIncidents = parse_renewlondon(gisData, apiData)
		if not apiData:
			print msg
			msg_log(curUnixTime, msg)
			return False
	except:
		print msg
		msg_log(curUnixTime, msg)
		return False

	return dIncidents


# ##########################################################################################################
# DEFINED FUNCTIONS
# ##########################################################################################################

# MODULE FUNCTIONS
# ----------------

# Function to Parse Renew London Data
def parse_renewlondon(gisData, apiData):
	# Connect to SQL Database
	conn = sql.connect(sqlDBname) # Make connection
	c = conn.cursor() # Create cursor
	c.execute("DELETE FROM gisdata") # Remove all GIS data records
	c.execute("DELETE FROM disruptions") # Remove all Disruption data records
	conn.commit() # Commit SQL Changes

	# Query GIS Information by ID
	for incident in gisData['features']:
		sSQL = "INSERT INTO gisdata VALUES ("
		sSQL += str(incident["id"]) + ","
		sSQL += "'" + coord_to_poly(incident["geometry"]["coordinates"]) + "',"
		sSQL += "'" + incident["properties"]["Street"] + "',"
		sSQL += str(incident["properties"]["StartDate"] / 1000) + ","
		sSQL += str(incident["properties"]["EndDate"] / 1000) + ")"
		#print sSQL
		c.execute(sSQL)
		conn.commit() # Commit SQL Changes

	# Query Data Details by ID
	for incident in apiData['Ongoing']:
		sSQL = "INSERT INTO disruptions VALUES ("
		sSQL += str(incident["Id"]) + ","
		sSQL += "'" + chk_description(incident["WorkTypes"]) + "',"
		sSQL += "'" + chk_short_description(incident["Impacts"]) + "',"
		sSQL += "'" + chk_type(incident["RoadClosed"]) + "')"
		#print sSQL
		c.execute(sSQL)
		conn.commit() # Commit SQL Changes

	# Create Data Hash List
	lChecksum = []
	c.execute("SELECT * FROM gisdata INNER JOIN disruptions ON disruptions.id = gisdata.id") # Join tables on common ID
	for row in c:
		sHash = calc_sha256_hash(row) # Calculate Hash from Current Data
		lChecksum.append({
			"id": row[0],
			"sha256": sHash
			})
		#print lChecksum

	# Query and Update Hash Checksum Table
	for row in lChecksum:
		c.execute("SELECT * FROM checksum WHERE id=" + str(row["id"]))
		lResults  = c.fetchall()
		if len(lResults) > 0:
			if len(lResults) > 1:
				msg_log(curUnixTime, "WARNING: Multiple checksum database records found for ID " + str(row["id"]) + "!!")
			sSQL = "UPDATE checksum SET "
			sSQL += "accesstime=" + str(curUnixTime)
			if lResults[0][4] != row["sha256"]: # Check if cursor hash NOT same as new checksum hash
				sSQL += ", updatetime=" + str(curUnixTime)
				sSQL += ", sha256='" + row["sha256"] + "'"
			sSQL += " WHERE id=" + str(row["id"])
		else:
			sSQL = "INSERT INTO checksum VALUES ("
			sSQL += str(row["id"]) + "," # id
			sSQL += str(curUnixTime) + "," # accesstime
			sSQL += str(curUnixTime) + "," # creationtime
			sSQL += str(curUnixTime) + "," # updatetime
			sSQL += "'" + row["sha256"] + "')" #sha256
		#print sSQL
		c.execute(sSQL)
		conn.commit() # Commit SQL Changes
	c.execute("DELETE FROM checksum WHERE accesstime<" + str(curUnixTime)) # Remove all Disruption data records
	conn.commit() # Commit SQL Changes8

	# Inner Join and Aggregate Database Data
	c.execute("SELECT * FROM gisdata INNER JOIN disruptions ON disruptions.id = gisdata.id INNER JOIN checksum ON disruptions.id = checksum.id")
	lResults  = c.fetchall()
	#print lResults
	if len(lResults) > 0:
		dIncidents = create_incidents(lResults) # Create Incidents Dictionary
	else:
		msg_log(curUnixTime, "ERROR: Final database inner join returned zero results!!")
		return False # No data available from query

	# Close SQL Database
	conn.close()

	# Log Database Changes Completed
	msg_log(curUnixTime, "SUCCESS: Database successfully updated " + str(len(lResults)) + " records!!")

	return dIncidents

# Function to Query Incident Details
def query_details():
	urllib3.disable_warnings() # Disable SSL Warnings from Renew London API
	http = urllib3.PoolManager()
	response = http.request("GET", apiRLdisruptions)
	try:
		if response.status == 200:
			return json.loads(response.data)
		else:
			return False
	except:
		msg_log(curUnixTime, "ERROR: API Disruptions query did not complete!!")
		return False

# Function to Query GIS Data
def query_gis():
	try:
		# Initialize Virtual Display
		display = Display(visible=0, size=(800, 600))
		display.start()
		# Selenium Webdriver Options and Start
		options = webdriver.ChromeOptions()
		options.add_argument('--no-sandbox')
		# Access and Scrape Main Website
		driver = webdriver.Chrome(chrome_options=options)
		driver.get(urlRlmain) # Load main website
		time.sleep(secSleep) # Pause to allow website data to load
		gisData = driver.execute_script(apiJSobj) # Scrape GIS Data
		#print gisData
		time.sleep(secSleep)
		driver.close() # Close Webdriver
		display.sendstop() # Stop Virtual Display
		return gisData
	except:
		msg_log(curUnixTime, "ERROR: GIS Scrape query did not complete!!")
		return False

# HELPER (MONKEY) FUNCTIONS
# -------------------------

# Function to Calculate SHA256 Hash
def calc_sha256_hash(tRow): # Input Tuple Row and Pull Offset Values
	sData = str(tRow[0]) # id
	sData += tRow[1] # polyline
	sData += tRow[2] # street
	sData += str(tRow[3]) # starttime
	sData += str(tRow[4]) # endtime
	sData += tRow[6] # description
	sData += tRow[7] # short_description
	sData += tRow[8] # type
	#print sData
	return hashlib.sha256(sData).hexdigest() # Create Unique String from Aggregated Data

# Function to Check Description for Default Value
def chk_description(isValue):
	if isValue:
		return isValue
	else:
		return def_description

# Function to Check Short Description for Default Value
def chk_short_description(isValue):
	if isValue:
		return isValue
	else:
		return def_short_description

# Function to Check Incident Type
def chk_type(isClosed):
	if isClosed:
		return "ROAD_CLOSED"
	else:
		return "CONSTRUCTION"

# Function to Convert GIS Coordinates to Polyline String
def coord_to_poly(lCoord):
	sPolyline = ""
	first = True
	for xy in lCoord:
		if first:
			first = False
		else:
			sPolyline += " "
		sPolyline += str(xy[1]) + " " + str(xy[0])
	return sPolyline

# Function to Create Incidents Dictionary
def create_incidents(lResults):
	dIncidents = {"timestamp": datetime_in_iso(curUnixTime), "incident": []}
	for incident in lResults:
		dIncidents["incident"].append({
			"id": incident[0],
			"creationtime": datetime_in_iso(incident[11]),
			"updatetime": datetime_in_iso(incident[12]),
			"type": incident[8],			
			"description": incident[6],
			"short_description": incident[7],
			"location": {
				"street": incident[2],
				"polyline": incident[1],
				"direction": "BOTH_DIRECTIONS"
				},
			"starttime": datetime_in_iso(incident[3]),
			"endtime": datetime_in_iso(incident[4]),
			"source": {
				"reference": "RenewLondon",
				"url": "https://apps.london.ca/RenewLondon",
				"name": "Corporation of the City of London"
				}
			})
	return dIncidents

# Function to Convert Date/Time String to ISO 8601 Format
def datetime_in_iso(ts=time.time()):
	ts = parser.parse(datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'))
	return ts.replace(microsecond=0).isoformat() + '-0' + str(time.timezone / 3600) + ':00'

# Function to Log Error to File
def msg_log(timestamp, msg):
	if "ERROR" in msg:
		msgcolor = "color:rgb(255, 0, 0);"
	elif "WARNING" in msg:
		msgcolor = "color:rgb(255, 165, 0);"
	else:
		msgcolor = "color:rgb(0, 100, 0);"
	logstr = "<span style='" + msgcolor + "'>" + datetime_in_iso(timestamp) + "&nbsp;&nbsp;&nbsp;" + msg + "</span><br />\n"
	with open(fMsgLog, "a") as fh:
		fh.write(logstr)
	return

# NAMESPACE CALL (DO NOT MODIFY)
# ------------------------------
if __name__ == "__main__":
	update()


# ##########################################################################################################
# END OF SCRIPT
# ##########################################################################################################