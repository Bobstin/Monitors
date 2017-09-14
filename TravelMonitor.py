#import tweepy
from twython import TwythonStreamer
import time
import os
import psycopg2
import urllib.parse as urlparse
import datetime
import sendgrid
from sendgrid.helpers.mail import *

consumer_key = 	os.environ.get('consumer_key')
consumer_secret = 	os.environ.get('consumer_secret')

access_token = os.environ.get('access_token')
access_token_secret = os.environ.get('access_token_secret')

DatabaseURL = os.environ.get('DATABASE_URL')

SendGridAPIKey=os.environ.get('SENDGRID_API_KEY')

#These are not hardcoded so that when run locally it will trigger on a test twitter account
UserToFollow = os.environ.get('UserToFollow')
TargetAuthor = os.environ.get('TargetAuthor')

#auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
#auth.set_access_token(access_token, access_token_secret)

#api = tweepy.API(auth)

class FlightStatusListenerClass(TwythonStreamer):

	def on_success(self, status):
		#print(status)
		#Defaults to '' in case that the status doesn't have the required element
		TweetAuthor = status.get('user',{'screen_name':''}).get('screen_name','')
		TweetText =  status.get('text','')
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
		AllKeywords = {
			"NYC":['new york','laguardia','lga','jfk','newark','ewr','nyc',' ny ','business'],
			"SF":['san francisco','sfo','sjc','sf','oak','business'],
			"Boston":['boston','logan','bos','business'],
			"Chicago":['chicago','ord','mdw','business'],
			"Philadelphia":['philadelphia','phl','philly'],
		}



		try:
			#Checks the tweet for each of the triggers
			#Checks if the author is TheFlightDeal
			if TweetAuthor == TargetAuthor: WrittenByTFD = True

			#Checks to see if any keywords are present
			if any(any(Key in LowerTweetText for Key in LocationKeywords) for LocationKeywords in AllKeywords.values()): ContainsKeyWord = True

			#Ignores replies
			if 	status.get('in_reply_to_status_id','') != None: IsAReply = True

			#must have the hashtag airfaire deal
			if '#airfare deal' in LowerTweetText: IsADeal = True

			#Uncomment the lines below to help with debugging
			#print ('WrittenByTFD:'+str(WrittenByTFD))
			#print ('ContainsKeyWord:'+str(ContainsKeyWord))
			#print ('IsAReply:'+str(IsAReply))
			#print ('IsADeal:'+str(IsADeal))

			#Isolates the destination from the tweet
			#Looks for a "-" as the start of the destination, and
			#ends it at "(" or a ". $", whatever comes first
			DestStart=TweetText.find("-")
			if TweetText.find(". $",DestStart)!=-1:
				if TweetText.find("(",DestStart)!=-1:
					DestEnd=min(TweetText.find(". $",DestStart),TweetText.find("(",DestStart))
				else:
					DestEnd=TweetText.find(". $",DestStart)
			else:
				DestEnd=TweetText.find("(",DestStart)
			
			if DestEnd != -1: print (TweetText[DestStart+2:DestEnd])


			if WrittenByTFD and ContainsKeyWord and ~IsAReply and IsADeal:
				#If the tweet was written by the flight deal, contains a keyword, and is not a reply, emails it out
				print('Emailing Tweet - ' + TweetAuthor + ": " + TweetText + '\n')

				#Connects to the database to find what users to send the email to
				#Uses a local database if needed
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
					Subject = "New deal detected by Flight Deal Monitor: "+TweetText[DestStart+2:DestEnd]
				else:
					Subject = "New deal detected by Flight Deal Monitor"

				#Sends the email, looping through all of the regions where a keyword was found
				for Region in AllKeywords:
					if any(Key in LowerTweetText for Key in AllKeywords[Region]):
						cur.execute("""SELECT email FROM users WHERE want_travel ='t' AND travel_region = '{}';""".format(Region))
						emails = cur.fetchall()
						#print(emails)
						#print(emailbody)
						#print(Subject)
						for email in emails:
							SendGrid_Email("flightdealmonitor@gmail.com",email[0],Subject,emailbody)
			else:
				print('Ignoring Tweet - ' + TweetAuthor + ": " + TweetText + '\n')

		except Exception as e:
			print (e)


	def on_error(self,status_code,data):
		print ('Error code recieved')
		print (status_code)
		print (data)
		error_email_body = "There has been an error in the flight deal monitor, with error code " + str(status_code)
		SendGrid_Email("flightdealmonitor@gmail.com","flightdealmonitor@gmail.com","ERROR: Flight Deal Monitor",error_email_body)
		if status_code == 420:
			print ('I was disconnected by Twitter')
			self.disconnect()
			#return False


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
	#Waits 5 minutes, so that restarting doesn't trigger a 420 error
	print("Waiting 5 minutes to avoid 420 (rate limiting) error")
	StartUpTime = 0
	
	while StartUpTime <= 270:
		time.sleep(30)
		StartUpTime = StartUpTime +30
		if StartUpTime < 300: print("Still waiting, " + str(300-StartUpTime) + " seconds remaining")
		if StartUpTime == 300: print("Done waiting!")

	#Connects to Twitter streaming API
	print("Connecting to Twitter streaming api")
	FlightStatusStream = FlightStatusListenerClass(consumer_key, consumer_secret,access_token,access_token_secret)

	#Need to filter on the user ID of @TheFlightDeal
	print("Following "+UserToFollow)
	FlightStatusStream.statuses.filter(follow=UserToFollow)
	
except Exception as e:
	print (e)
	print ("This is where the error is being caught")
	raise

while True:
	timestamp = time.strftime("\n%m/%d/%y %H:%M:")
	print (timestamp)
	print ('Still Running\n')

	#Waits until the top of the next hour to print the still running message
	currenttime = datetime.datetime.today()
	roundedtime = datetime.datetime(currenttime.year,currenttime.month,currenttime.day,currenttime.hour)
	waittime = datetime.timedelta(hours = 1)
	nextrun = roundedtime + waittime
	time.sleep((nextrun-currenttime).total_seconds())
