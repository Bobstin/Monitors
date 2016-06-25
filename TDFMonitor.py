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
import urlparse

GmailPass = os.environ.get('GmailPass')
DBPass = os.environ.get('DBPass')
TDFUsername = os.environ.get('TDFUsername')
TDFPass = os.environ.get('TDFPass')
DatabaseURL = os.environ.get('DATABASE_URL')
SendGridPass=os.environ.get('SENDGRID_PASSWORD')
SendGridUsername=os.environ.get('SENDGRID_USERNAME')

def SendGrid_Email(user,recipient,subject,body):
	sg = sendGrid.SendGridClient(SendGridUsername,SendGridPass)
	message = sendgrid.Mail()
	message.add_to(recipient)
	message.set_subject(subject)
	message.set_text(body)
	message.set_from(user)
	status, msg = sg.send(message)


def DetectNewShows(newhtml):
	print "Checking for new shows"
	
	#Connects to the database, creates a cursor
	if DatabaseURL=='127.0.0.1':
		conn = psycopg2.connect(database="monitordb",user="tdfmonitor",password=DBPass,host=DatabaseURL,port="5432")
	else:
		urlparse.uses_netloc.append("postgres")
		url = urlparse.urlparse(os.environ["DATABASE_URL"])

		conn = psycopg2.connect(
	    	database=url.path[1:],
	   		user=url.username,
	    	password=url.password,
	    	host=url.hostname,
	    	port=url.port
		)

	
	cur = conn.cursor()
	
	#uses beautifulsoup to process the html
	newprocessedhtml = BeautifulSoup(newhtml,'lxml')
	
	#parses the html for the show names
	newshows = newprocessedhtml.find_all('div',class_='ListingShowTitle')
	
	#clears the previous pull
	cur.execute("DELETE FROM latest_tdf_pull;")

	#Sets the the line for how long a show needs to be missing before sending
	currenttime = datetime.datetime.now()
	lag = datetime.timedelta(hours = 24)
	oldline = currenttime - lag
	#print oldline

	#inserts the latest pull into the database
	for show in newshows:
		#print show.text
		cur.execute("INSERT INTO latest_tdf_pull(show_name,last_found) VALUES (%s,%s);",[show.text,datetime.datetime.now()])

	#compares the two tables to identify what is new
	cur.execute("""SELECT latest_tdf_pull.show_name FROM latest_tdf_pull LEFT OUTER JOIN tdf_shows ON (latest_tdf_pull.show_name = tdf_shows.show_name)
	WHERE tdf_shows.show_name is null
	OR tdf_shows.last_found<%s;""",[oldline])
	showstosend = cur.fetchall()
	#print showstosend 

	#Adds the missing rows
	cur.execute("""INSERT INTO tdf_shows
	SELECT latest_tdf_pull.show_name FROM latest_tdf_pull LEFT OUTER JOIN tdf_shows ON (latest_tdf_pull.show_name = tdf_shows.show_name)
	WHERE tdf_shows.show_name is null""")
	
	#updates the tdf_shows table with the new last_found times
	cur.execute("""UPDATE tdf_shows
	SET last_found = latest_tdf_pull.last_found
	FROM latest_tdf_pull
	WHERE tdf_shows.show_name = latest_tdf_pull.show_name;""")

	#Commits the changes to the database
	conn.commit()

	if len(showstosend) > 0:
		#starts to draft the email
		emailbody ="TDF Monitor has found a new show is being offered on TDF:\n\n"

		#Adds list of shows that were found
		for show in showstosend:
			emailbody = emailbody + "\t" + show[0] + "\n"
			print show[0]

		emailbody = emailbody + "\nBest,\nTDF Monitor"

		#queries the database for the list of emails of users that want tdf updates
		cur.execute("""SELECT email FROM users WHERE want_tdf ='t' ;""")
		emails = cur.fetchall()

		#Sends the email
		#print emailbody
		for email in emails:
			SendGrid_Email("tdfmonitor@gmail.com",email[0],"New show detected by TDF Monitor",emailbody)
		
	else:
		print "No new shows detected"


def TDFPull():
	print "Pulling html from TDF"
	#Go to website and login
	#driver = webdriver.Ie()
	driver = webdriver.PhantomJS()

	#Waits 5 seconds before giving up on finding elements
	driver.implicitly_wait(5)

	driver.get('http://secure2.tdf.org')
	username = driver.find_element_by_name('LOGON_EMAIL')
	username.clear()
	username.send_keys(TDFUsername)
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

while True:
	#Prints a timestamp
	timestamp = time.strftime("%m/%d/%y %H:%M:")
	print timestamp.encode('utf-8')

	#Pulls the HTML from the TDF website
	newhtml = TDFPull()

	#Compares the current and previous shows
	DetectNewShows(newhtml)

	#Waits for an hour to check again
	print "Going back to sleep\n"
	waitonehour()