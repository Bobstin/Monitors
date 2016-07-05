import tweepy
import time
import os
import psycopg2
import urlparse
import datetime
import sendgrid
from sendgrid.helpers.mail import *

consumer_key = 	os.environ.get('consumer_key')
consumer_secret = 	os.environ.get('consumer_secret')

access_token = os.environ.get('access_token')
access_token_secret = os.environ.get('access_token_secret')

TravelGmailPass = os.environ.get('TravelGmailPass')

DatabaseURL = os.environ.get('DATABASE_URL')

SendGridAPIKey=os.environ.get('SENDGRID_API_KEY')

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

api = tweepy.API(auth)

class FlightStatusListenerClass(tweepy.StreamListener):

	def on_status(self, status):
		TweetAuthor = status.author.screen_name.encode('ascii','ignore')
		TweetText =  status.text.encode('ascii', 'ignore')
		print TweetAuthor + ": " + TweetText
		LowerTweetText = TweetText.lower()
		
		#Defaults all triggers to false
		WrittenByTFD = False
		ContainsKeyWord = False
		IsAReply = False
		ContainsNYCKeyWord = False
		ContainsSFKeyWord = False
		IsADeal = False

		#Sets the words to look for in each region
		#NOTE: all keywords should be lower case
		NYCKeywords = ['new york','laguardia','lga','jfk','newark','ewr','nyc',' ny ']
		SFKeywords = ['san francisco','sfo','sjc','sf','oak']
		AllKeywords = NYCKeywords + SFKeywords

		try:
			#Checks the tweet for each of the triggers
			if TweetAuthor == 'TheFlightDeal': WrittenByTFD = True

			if any(x in LowerTweetText for x in AllKeywords): ContainsKeyWord = True
			if any(x in LowerTweetText for x in NYCKeywords): ContainsNYCKeyWord = True
			if any(x in LowerTweetText for x in SFKeywords): ContainsSFKeyWord = True

			if 	status.in_reply_to_status_id != None: IsAReply = True

			if '#airfare deal' in LowerTweetText: IsADeal = True

			#print 'WrittenByTFD:'+str(WrittenByTFD)
			#print 'ContainsKeyWord:'+str(ContainsKeyWord)
			#print 'IsAReply:'+str(IsAReply)
			#print 'IsADeal:'+str(IsADeal)

			DestStart=TweetText.find("-")
			if DestStart != -1: DestEnd=TweetText.find(".",DestStart)
			if DestEnd != -1: print  TweetText[DestStart+2:DestEnd]


			if WrittenByTFD and ContainsKeyWord and ~IsAReply and IsADeal:
				#If the tweet was written by the flight deal, contains a keyword, and is not a reply, emails it out
				print 'Emailing Tweet\n'

				


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

				#Constructs the body and subject of the email
				emailbody ="Flight Deal Monitor has found a deal on @TheFlightDeal:\n\n" + TweetText + '\n\nBest,\nFlight Deal Monitor'
				if DestStart!=-1 and DestEnd !=-1:
					Subject = "New deal detected by Flight Deal Monitor:"+TweetText[DestStart+2:DestEnd]
				else:
					Subject = "New deal detected by Flight Deal Monitor"

				#Sends the email, first to the NYC region, and then to SF
				if ContainsNYCKeyWord:
					cur.execute("""SELECT email FROM users WHERE want_travel ='t' AND travel_region = 'NYC';""")
					emails = cur.fetchall()
					for email in emails:
						SendGrid_Email("flightdealmonitor@gmail.com",email[0],Subject,emailbody)

				if ContainsSFKeyWord:
					cur.execute("""SELECT email FROM users WHERE want_travel ='t' AND travel_region = 'SF';""")
					emails = cur.fetchall()
					for email in emails:
						SendGrid_Email("flightdealmonitor@gmail.com",email[0],Subject,emailbody)

			else:
				print 'Ignoring Tweet\n'

		except Exception as e:
			print e


	def on_error(self,status_code):
		print 'Error code recieved'
		print status_code
		error_email_body = "There has been an error in the flight deal monitor, with error code " + str(status_code)
		SendGrid_Email("flightdealmonitor@gmail.com","flightdealmonitor@gmail.com","ERROR: Flight Deal Monitor",error_email_body)
		if status_code == 420:
			print 'I was disconnected by Twitter'
			return False


def SendGrid_Email(user,recipient,subject,body):
	sg = sendgrid.SendGridAPIClient(apikey=SendGridAPIKey)
	from_email = Email(user)
	to_email = Email(recipient)
	content = Content("text/plain",body)
	mail = Mail(from_email,subject,to_email,content)
	response = sg.client.mail.send.post(request_body=mail.get())
	#print(response.status_code)
	#print(response.body)
	#print(response.headers)


try:
	FlightStatusListener = FlightStatusListenerClass()
	FlightStatusStream = tweepy.Stream(auth = api.auth, listener = FlightStatusListener)
	#Need to filter on the user ID of @TheFlightDeal
	FlightStatusStream.filter(follow=['352093320'], async = True)
	
except Exception as e:
	print e
	print "this is where the error is being caught"

while True:
	timestamp = time.strftime("\n%m/%d/%y %H:%M:")
	print timestamp
	print 'Still Running\n'

	#Waits until the top of the next hour to print the still running message
	currenttime = datetime.datetime.today()
	roundedtime = datetime.datetime(currenttime.year,currenttime.month,currenttime.day,currenttime.hour)
	waittime = datetime.timedelta(hours = 1)
	nextrun = roundedtime + waittime
	time.sleep((nextrun-currenttime).total_seconds())
