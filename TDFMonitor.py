from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
import time
from bs4 import BeautifulSoup
import smtplib
import datetime
import os
import psycopg2


def DetectNewShows(newhtml):
	print "Checking for new shows"
	#opens the old html file and the log
	oldhtml = open("C:\TDF Check\oldhtml.txt","r")
	log = open("C:\TDF Check\log.txt","a")
	timestamp = time.strftime("\n%m/%d/%y %H:%M:\n")
	log.write(timestamp.encode('utf-8'))

	#uses beautifulsoup to process the html
	oldprocessedhtml = BeautifulSoup(oldhtml,'lxml')
	newprocessedhtml = BeautifulSoup(newhtml,'lxml')
	
	#parses the html for the show names
	oldshows = oldprocessedhtml.find_all('div',class_='ListingShowTitle')
	newshows = newprocessedhtml.find_all('div',class_='ListingShowTitle')

	#starts to draft the email; assumes to start that no email is required
	emailbody ="TDF Monitor has found a new show is being offered on TDF:\n\n"
	needtosendemail = 0

	#compares the list of new shows, and detects if any is missing.
	#If one is, adds it to the email, and flags that an email is needed
	for show in newshows:
		if show in oldshows:
			pass
		else:
			needtosendemail=1
			emailbody = emailbody + "\t" + show.text + "\n"
			log.write(show.text+"\n")

	emailbody = emailbody + "\nBest,\nTDF Monitor"
	#emails = ['***REMOVED***', '***REMOVED***','***REMOVED***','***REMOVED***']
	emails = ['***REMOVED***']
	

	#If needed, sends the email
	if needtosendemail == 1:
		#print emailbody
		for email in emails:
			send_email("tdfmonitor@gmail.com",GmailPass,email,"New show detected by TDF Monitor",emailbody)
		
	else:
		#print "No new shows detected"
		#send_email("tdfmonitor@gmail.com","***REMOVED***","***REMOVED***","New show detected by TDF Monitor",emailbody)
		log.write("No new shows detected\n")

	#saves the new html to the old file for later comparisons
	oldhtml.close()
	oldhtml = open("C:\TDF Check\oldhtml.txt","wb")
	oldhtml.write(newhtml.encode('utf-8'))

def TDFPull():
	print "Pulling html from TDF"
	#Go to website and login
	#driver = webdriver.Ie()
	driver = webdriver.PhantomJS(executable_path='C:\TDF Check\phantomjs\PhantomJS.exe')
	driver.get('http://secure2.tdf.org')
	username = driver.find_element_by_name('LOGON_EMAIL')
	username.clear()
	username.send_keys("***REMOVED***")
	username = driver.find_element_by_name('LOGON_PASSWORD')
	username.send_keys(TDFPass)

	driver.find_element_by_class_name('DefaultFormButton').click()
	driver.get('https://members.tdf.org/welcome/currentofferings.html')
	
	allshows = driver.page_source
	driver.quit()
	return allshows	

def send_email(user, pwd, recipient, subject, body):
	print "Sending Email"
	gmail_user = user
	gmail_pwd = pwd
	FROM = user
	TO = recipient if type(recipient) is list else [recipient]
	SUBJECT = subject
	TEXT = body

	# Prepare actual message
	message = """\From: %s\nTo: %s\nSubject: %s\n\n%s
	""" % (FROM, ", ".join(TO), SUBJECT, TEXT)

	server_ssl = smtplib.SMTP_SSL("smtp.gmail.com", 465)
	server_ssl.ehlo() # optional, called by login()
	server_ssl.login(gmail_user, gmail_pwd)  
	server_ssl.sendmail(FROM, TO, message)
	server_ssl.close()
	#print 'successfully sent the mail'

def waitonehour():
	#Calculates the next run time (top of the next hour). 
	#Note that waiting an hour would cause time drift (thus the rounding)
	currenttime = datetime.datetime.today()
	roundedtime = datetime.datetime(currenttime.year,currenttime.month,currenttime.day,currenttime.hour)
	waittime = datetime.timedelta(hours = 1)
	nextrun = roundedtime + waittime
	time.sleep((nextrun-currenttime).total_seconds())

#Connect to database
DBConn = psycopg2.connect(database="testdb",user="tdfmonitor",password=DBPass,host="127.0.0.1",port="5432")
print 'Opened DB successfully'

#Executes a query
cur = DBConn.cursor()
cur.execute("SELECT id,name,email,want_tdf,want_travel,travel_region from USERS")
users = cur.fetchall()
for user in users:
	print "ID = ", user[0]
	print "name = ", user[1]
	print "email = ", user[2]

while True:
	print datetime.datetime.today()
	newhtml = TDFPull()
	DetectNewShows(newhtml)
	print "Going back to sleep\n"
	waitonehour()


print "end"
