import tweepy
import time
import smtplib

consumer_key = 	'***REMOVED***'
consumer_secret = 	'***REMOVED***'

access_token = '***REMOVED***'
access_token_secret = '***REMOVED***'

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

api = tweepy.API(auth)

#FlightDeal = api.get_user('TheFlightDeal')

#print FlightDeal.screen_name
#print FlightDeal.followers_count

#FlightStatuses = api.user_timeline('TheFlightDeal')
#print FlightStatuses

#for tweet in FlightStatuses:
#	print tweet.text

class FlightStatusListenerClass(tweepy.StreamListener):

	def on_status(self, status):
		TweetAuthor = status.author.screen_name.encode('ascii','ignore')
		TweetText =  status.text.encode('ascii', 'ignore')
		log = open("C:\Travel Monitor\log.txt","a")
		print TweetAuthor + ": " + TweetText
		log.write(TweetAuthor + ": " + TweetText+'\n')
		
		WrittenByTFD = False
		ContainsKeyWord = False
		IsAReply = False
		AllKeywords = ['New York','Laguardia','LGA','JFK','Newark','EWR','NYC','Business','NY']

		

		try:
			if TweetAuthor == 'TheFlightDeal': WrittenByTFD = True
			if any(x in TweetText for x in AllKeywords): ContainsKeyWord = True
			if 	status.in_reply_to_status_id != None: IsAReply = True


			if WrittenByTFD and ContainsKeyWord and ~IsAReply:
				print 'Emailing Tweet\n'
				log.write('Emailing Tweet\n\n')
				timestamp = time.strftime("\n%m/%d/%y %H:%M:")
				print timestamp
				log.write(timestamp.encode('utf-8')+'\n')
				emailbody ="Flight Deal Monitor has found a deal on @TheFlightDeal:\n\n" + TweetText + '\n\nBest,\nFlight Deal Monitor'
				send_email("flightdealmonitor@gmail.com","***REMOVED***","***REMOVED***","New deal detected by Flight Deal Monitor",emailbody)
				send_email("flightdealmonitor@gmail.com","***REMOVED***","***REMOVED***","New deal detected by Flight Deal Monitor",emailbody)
				send_email("flightdealmonitor@gmail.com","***REMOVED***","***REMOVED***","New deal detected by Flight Deal Monitor",emailbody)
			else:
				print 'Ignoring Tweet\n'
				log.write('Ignoring Tweet\n\n')
				log.close()

		except Exception as e:
			print e
			send_email("flightdealmonitor@gmail.com","***REMOVED***","***REMOVED***","ERROR: Flight Deal Monitor",e)
			log.write(e+'\n')
			log.close()
	

	def on_error(self,status_code):
		log = open("C:\Travel Monitor\log.txt","a")
		print 'Error code recieved'
		print status_code
		error_email_body = "There has been an error in the flight deal monitor, with error code " + str(status_code)
		log.write(error_email_body+'\n')
		log.close()
		send_email("flightdealmonitor@gmail.com","***REMOVED***","***REMOVED***","ERROR: Flight Deal Monitor",error_email_body)
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
	#print 'successfully sent the mail'


try:
	FlightStatusListener = FlightStatusListenerClass()
	FlightStatusStream = tweepy.Stream(auth = api.auth, listener = FlightStatusListener)
	#Need to filter on the user ID of @TheFlightDeal
	FlightStatusStream.filter(follow=['352093320'], async = True)
except Exception as e:
	print e
	print "this is where the error is being caught"

while True:
	log = open("C:\Travel Monitor\log.txt","a")
	timestamp = time.strftime("\n%m/%d/%y %H:%M:")
	log.write(timestamp.encode('utf-8'))
	log.write('\nStill Running\n\n')
	log.close()
	print timestamp
	print 'Still Running\n'
	time.sleep(3600)