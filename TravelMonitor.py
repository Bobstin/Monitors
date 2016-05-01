import tweepy
import time
import smtplib
import os
import psycopg2
import urlparse

consumer_key = 	os.environ.get('consumer_key')
consumer_secret = 	os.environ.get('consumer_secret')

access_token = os.environ.get('access_token')
access_token_secret = os.environ.get('access_token_secret')

TravelGmailPass = os.environ.get('TravelGmailPass')

DatabaseURL = os.environ.get('DATABASE_URL')

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

api = tweepy.API(auth)

class FlightStatusListenerClass(tweepy.StreamListener):

	def on_status(self, status):
		TweetAuthor = status.author.screen_name.encode('ascii','ignore')
		TweetText =  status.text.encode('ascii', 'ignore')
		print TweetAuthor + ": " + TweetText
		TweetText = TweetText.lower()
		
		#Defaults all triggers to false
		WrittenByTFD = False
		ContainsKeyWord = False
		IsAReply = False

		#Sets the words to look for in each region
		#NOTE: all keywords should be lower case
		NYCKeywords = ['new york','laguardia','lga','jfk','newark','ewr','nyc','ny']
		SFKeywords = ['san Francisco','sfo','sjc','sf','oak']
		AllKeywords = NYCKeywords + SFKeywords

		try:
			#Checks the tweet for each of the triggers
			#if TweetAuthor == 'TheFlightDeal': WrittenByTFD = True
			if TweetAuthor == 'bobstin': WrittenByTFD = True
			if any(x in TweetText for x in AllKeywords): ContainsKeyWord = True
			if any(x in TweetText for x in NYCKeywords): ContainsNYCKeyWord = True
			if any(x in TweetText for x in SFKeywords): ContainsSFKeyWord = True
			if 	status.in_reply_to_status_id != None: IsAReply = True


			if WrittenByTFD and ContainsKeyWord and ~IsAReply:
				#If the tweet was written by the flight deal, contains a keyword, and is not a reply, emails it out
				print 'Emailing Tweet\n'
				timestamp = time.strftime("\n%m/%d/%y %H:%M:")
				print timestamp

				#Connects to the database to find what users to send the email to
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

				#Constructs the body of the email
				emailbody ="Flight Deal Monitor has found a deal on @TheFlightDeal:\n\n" + TweetText + '\n\nBest,\nFlight Deal Monitor'

				if ContainsNYCKeyWord:
					cur.execute("""SELECT email FROM users WHERE want_travel ='t' AND travel_region = 'NYC';""")
					emails = cur.fetchall()
					for email in emails:
						send_email("flightdealmonitor@gmail.com",TravelGmailPass,email,"New deal detected by Flight Deal Monitor",emailbody)

				if ContainsSFKeyWord:
					cur.execute("""SELECT email FROM users WHERE want_travel ='t' AND travel_region = 'SF';""")
					emails = cur.fetchall()
					for email in emails:
						send_email("flightdealmonitor@gmail.com",TravelGmailPass,email,"New deal detected by Flight Deal Monitor",emailbody)

			else:
				print 'Ignoring Tweet\n'

		except Exception as e:
			print e


	def on_error(self,status_code):
		print 'Error code recieved'
		print status_code
		error_email_body = "There has been an error in the flight deal monitor, with error code " + str(status_code)
		send_email("flightdealmonitor@gmail.com",TravelGmailPass,"flightdealmonitor@gmail.com","ERROR: Flight Deal Monitor",error_email_body)
		if status_code == 420:
			print 'I was disconnected by Twitter'
			return False


def send_email(user, pwd, recipient, subject, body):
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
	#print 'successfully sent the email'


try:
	FlightStatusListener = FlightStatusListenerClass()
	FlightStatusStream = tweepy.Stream(auth = api.auth, listener = FlightStatusListener)
	#Need to filter on the user ID of @TheFlightDeal
	#FlightStatusStream.filter(follow=['352093320'], async = True)
	FlightStatusStream.filter(follow=['46830140'], async = True)
	
except Exception as e:
	print e
	print "this is where the error is being caught"

while True:
	timestamp = time.strftime("\n%m/%d/%y %H:%M:")
	print timestamp
	print 'Still Running\n'
	time.sleep(3600)