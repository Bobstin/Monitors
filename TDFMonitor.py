import time
import bs4
import smtplib
import datetime
import os
import psycopg2
import urllib.parse as urlparse
import sendgrid
from sendgrid.helpers.mail import Email, Content, Mail
import requests
import json

#GmailPass = os.environ.get('GmailPass')
DBPass = os.environ.get('DBPass')
TDFUsername = os.environ.get('TDFUsername')
TDFPass = os.environ.get('TDFPass')
DatabaseURL = os.environ.get('DATABASE_URL')
SendGridAPIKey=os.environ.get('SENDGRID_API_KEY')
TimePastHour=os.environ.get('TimePastHour')

def sendgrid_email(user,recipient,subject,body):
    sg = sendgrid.SendGridAPIClient(apikey=SendGridAPIKey)
    from_email = Email(user)
    to_email = Email(recipient)
    content = Content("text/plain",body)
    mail = Mail(from_email,subject,to_email,content)
    response = sg.client.mail.send.post(request_body=mail.get())


def detect_new_shows(new_shows):
    print ("Checking for new shows")
    
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
        
    #clears the previous pull
    cur.execute("DELETE FROM latest_tdf_pull;")

    #Sets the the line for how long a show needs to be missing before sending
    currenttime = datetime.datetime.now()
    lag = datetime.timedelta(hours = 24)
    oldline = currenttime - lag
    #print oldline

    #inserts the latest pull into the database
    for show in new_shows:
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
            print(show[0])

        emailbody = emailbody + "\nBest,\nTDF Monitor"

        #queries the database for the list of emails of users that want tdf updates
        cur.execute("""SELECT email FROM users WHERE want_tdf ='t' ;""")
        emails = cur.fetchall()

        #Sends the email
        #print emailbody
        for email in emails:
            sendgrid_email("tdfmonitor@gmail.com",email[0],"New show detected by TDF Monitor",emailbody)
        
    else:
        print("No new shows detected")


def TDF_pull():
    # Goes to the tdf website and gets the show list
    # This is complicated by the complex CSRF verification TDF does
    with requests.Session() as session:
        session = requests.Session()
        login_page = session.get('https://my.tdf.org/account/login')
        login_soup = bs4.BeautifulSoup(login_page.text, features='lxml')
        rvt = login_soup.find(attrs={'name': '__RequestVerificationToken'})['value']
        data = {'__RequestVerificationToken': rvt, 'PatronAccountLogin.Username': TDFUsername, 'PatronAccountLogin.Password': TDFPass}
        login_post = session.post('https://my.tdf.org/account/login?', data=data)
        payload = {'actionUrl': 'https://nycgw47.tdf.org/TDFCustomOfferings'}
        next_page = session.get('https://my.tdf.org/components/sharedsession', params=payload)
        next_page_soup = bs4.BeautifulSoup(next_page.text, features='lxml')
        epv = next_page_soup.find(id="EncryptedPayload_Value")['value']
        data = {'EncryptedPayload.Value': epv, 'ReturnUrl': ''}
        custom_offerings = session.post('https://nycgw47.tdf.org/TDFCustomOfferings', data=data)
        payload = {'handler': 'Performances'}
        shows = session.get('https://nycgw47.tdf.org/TDFCustomOfferings/Current', params=payload)

    shows_list = json.loads(shows.text)

    broadway_shows = []
    for show in shows_list:
        keywords = show['keywords']
        for keyword in keywords:
            if keyword['categoryName'] == 'Venue' and keyword['keywordName'] == 'Broadway':
                broadway_shows.append(show['title'])

    print(broadway_shows)

    return broadway_shows


def wait_one_hour():
    #Calculates the next run time (top of the next hour). 
    #Note that waiting an hour would cause time drift (thus the rounding)
    currenttime = datetime.datetime.today()
    roundedtime = datetime.datetime(currenttime.year,currenttime.month,currenttime.day,currenttime.hour)
    waittime = datetime.timedelta(hours = 1)
    nextrun = roundedtime + waittime
    time.sleep((nextrun-currenttime).total_seconds()+int(TimePastHour)*60)


if __name__ == '__main__':
    while True:
        #Prints a timestamp
        timestamp = time.strftime("%m/%d/%y %H:%M:")
        print (timestamp.encode('utf-8'))

        #Pulls the HTML from the TDF website
        new_shows = TDF_pull()

        #Compares the current and previous shows
        detect_new_shows(new_shows)

        #Waits for an hour to check again
        print ("Going back to sleep\n")
        wait_one_hour()