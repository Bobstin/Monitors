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
from string import Template

#GmailPass = os.environ.get('GmailPass')
DBPass = os.environ.get('DBPass')
TDFUsername = os.environ.get('TDFUsername')
TDFPass = os.environ.get('TDFPass')
DatabaseURL = os.environ.get('DATABASE_URL')
SendGridAPIKey = os.environ.get('SENDGRID_API_KEY')
TimePastHour = os.environ.get('TimePastHour')
PBP_username = os.environ.get('PBPUsername')
PBP_password = os.environ.get('PBPPass')

def sendgrid_email(user,recipient,subject,body):
    sg = sendgrid.SendGridAPIClient(apikey=SendGridAPIKey)
    from_email = Email(user)
    to_email = Email(recipient)
    content = Content("text/plain",body)
    mail = Mail(from_email,subject,to_email,content)
    response = sg.client.mail.send.post(request_body=mail.get())


def detect_new_shows(new_shows, website):
    print ("Checking for new shows")
    
    #Connects to the database, creates a cursor
    if DatabaseURL=='127.0.0.1':
        conn = psycopg2.connect(database="monitordb",user="postgres",password=DBPass,host=DatabaseURL,port="5432")
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
    cur.execute(f"DELETE FROM latest_{website}_pull;")

    #Sets the the line for how long a show needs to be missing before sending
    currenttime = datetime.datetime.now()
    lag = datetime.timedelta(hours = 24)
    oldline = currenttime - lag
    #print oldline

    #inserts the latest pull into the database
    for show in new_shows:
        show = show.replace("'","''") # Needed to escape single quotes
        cur.execute(f"INSERT INTO latest_{website}_pull(show_name,last_found) VALUES ('{show}','{datetime.datetime.now()}');")

    #compares the two tables to identify what is new
    cur.execute(f"""SELECT latest_{website}_pull.show_name FROM latest_{website}_pull LEFT OUTER JOIN {website}_shows ON (latest_{website}_pull.show_name = {website}_shows.show_name)
    WHERE {website}_shows.show_name is null
    OR {website}_shows.last_found<'{oldline}';""")
    shows_to_send = cur.fetchall()

    #Adds the missing rows
    cur.execute(f"""INSERT INTO {website}_shows
    SELECT latest_{website}_pull.show_name FROM latest_{website}_pull LEFT OUTER JOIN {website}_shows ON (latest_{website}_pull.show_name = {website}_shows.show_name)
    WHERE {website}_shows.show_name is null""")
    
    #updates the tdf_shows table with the new last_found times
    cur.execute(f"""UPDATE {website}_shows
    SET last_found = latest_{website}_pull  .last_found
    FROM latest_{website}_pull
    WHERE {website}_shows.show_name = latest_{website}_pull.show_name;""")

    #Commits the changes to the database
    conn.commit()

    if len(shows_to_send) > 0:
        #starts to draft the email
        email_body =f"{website} Monitor has found a new show is being offered on {website}:\n\n"

        #Adds list of shows that were found
        for show in shows_to_send:
            email_body = email_body + "\t" + show[0] + "\n"
            print(show[0])

        email_body = email_body + f"\nBest,\n{website} Monitor"

        #queries the database for the list of emails of users that want tdf updates
        cur.execute(f"""SELECT email FROM users WHERE want_{website} ='t' ;""")
        emails = cur.fetchall()

        #Sends the email
        #print emailbody
        for email in emails:
            sendgrid_email("tdfmonitor@gmail.com", email[0], f"New show detected by {website} Monitor", email_body)
        
    else:
        print(f"No new shows detected on {website}")


def TDF_pull():
    # Goes to the tdf website and gets the show list
    # This is complicated by the complex CSRF verification TDF does
    with requests.Session() as session:
        login_page = session.get('https://my.tdf.org/account/login')
        login_soup = bs4.BeautifulSoup(login_page.text, features='lxml')
        rvt = login_soup.find(attrs={'name': '__RequestVerificationToken'})['value']
        data = {'__RequestVerificationToken': rvt, 'PatronAccountLogin.Username': TDFUsername, 'PatronAccountLogin.Password': TDFPass}
        login_post = session.post('https://my.tdf.org/account/login?', data=data)
        page_for_cookie = session.get('https://nycgw47.tdf.org/TDFCustomOfferings')
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
        if keywords is not None:
            for keyword in keywords:
                if keyword['categoryName'] == 'Venue' and keyword['keywordName'] == 'Broadway':
                    broadway_shows.append(show['title'])

    return broadway_shows


def pbp_pull():
    with requests.Session() as session:
        data = {'email': PBP_username, 'password': PBP_password}
        login = session.post('https://www.play-by-play.com/login/action', data=data)
        soup = bs4.BeautifulSoup(login.text, features='lxml')
        shows = soup.find_all('div',{'class': 'product-content'})
        shows = [show.find('div',{'class': 'product-content__title'}).text.strip()
                 for show in shows
                 if show.find('div',{'class': 'product-content__title'}) is not None
                 and 'broadway' in show.find('div',{'class': 'product-content__meta'}).text.strip().lower()]

    return shows




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

        #Pulls the HTML from the TDF and PBP websites
        new_tdf_shows = TDF_pull()
        new_pbp_shows = pbp_pull()

        #Compares the current and previous shows
        detect_new_shows(new_tdf_shows, 'TDF')
        detect_new_shows(new_pbp_shows, 'PBP')

        #Waits for an hour to check again
        print ("Going back to sleep\n")
        wait_one_hour()