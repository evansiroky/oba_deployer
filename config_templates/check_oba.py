#!/usr/bin/env python

"""
Copyright 2015 Georgia Institute of Technology & Evan Siroky

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import ConfigParser
import csv
import datetime
import email
import json
import imaplib
import os
import smtplib
import time
import urllib2
import urllib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

CONFIG_FILENAME = '/home/ec2-user/conf/watchdog.ini'
CONFIG = ConfigParser.ConfigParser()
CONFIG.read(CONFIG_FILENAME)


def get_config(key):
    return CONFIG.get('DEFAULT', key)

# PARAMETERS

# Agency ids for agencies with realtime data.
REALTIME_AGENCIES = get_config('realtime_agencies').split(',')
# These people get an email every time there is an alert.
ALERT_LIST = get_config('alert_list').split(',')
# These people get an email every time that check_oba.py is run
REPORT_LIST = get_config('report_list').split(',')
FROM_ADDRESS = get_config('from_address')

DATA_DIR = get_config('data_dir')
CSV_STATUS_FILE = os.path.join(DATA_DIR, 'watchdog_status.csv')
REPORT_STATUS_FILE = os.path.join(DATA_DIR, 'watchdog_report_status.csv')
ROOT_URL = get_config('root_url')

# If 1, report, else don't.  index 0 = Monday, 6 = Sunday
DAYS_OF_WEEK_TO_REPORT = map(int, get_config('days_of_week_to_report').split(','))
# The hours when a report gets sent.  SPECIFY AT LEAST TWO HOURS
REPORT_HOURS = map(int, get_config('report_hours').split(','))
# The seconds after midnight that we start and stop checking
START_OF_DAY = int(get_config('start_of_day'))
END_OF_DAY = int(get_config('end_of_day'))

# Limiting factor for number of stops to cycle through
PCT_STOPS = int(get_config('percent_of_stops_to_check_in_each_agency'))

API_KEY = get_config('api_key')

IMAP_HOST = get_config('imap_host')
SMTP_HOST = get_config('smtp_host')
USERNAME = get_config('username')
PASSWORD = get_config('password')
#######################


def get_agencies(apiURL, attempts=0):

    base = apiURL + '/api/where/agencies-with-coverage.json?'
    query = urllib.urlencode(dict(key=API_KEY))

    try:
        response = urllib2.urlopen(base + query, timeout=30).read()
    except urllib2.HTTPError as e:
        return False, 'Received HTTP Error: {0}'.format(e.code)
    except IOError as e:
        if attempts > 3:
            return False, 'Unable to open:  ' + base + query
        else:
            time.sleep(20)
            # print 'get_agencies sleeping'
            return(get_agencies(apiURL, attempts + 1))

    except urllib2.URLError, e:
        return False, "Timeout when opening:  " + base + query

    try:
        data = json.loads(response)
    except ValueError:
        return False, 'NO JSON Data in get_agencies: ' + base + query
    except:
        return False, 'UNKNOWN ERROR in get_agencies' + base + query

    try:
        agencies = data['data']['list']
    except KeyError:
        return False, 'Agency list not formatted as expected: ' + base + query
    return True, agencies


def get_stops(apiURL, agency, attempts=0):

    base = apiURL + '/api/where/stop-ids-for-agency/' + agency['agencyId'] + '.json?'
    query = urllib.urlencode(dict(key=API_KEY))

    try:
        response = urllib.urlopen(base + query).read()
    except IOError:
        if attempts > 3:
            return False, 'Unable to open:  ' + base + query
        else:
            time.sleep(20)
            # print 'get_stops sleeping'
            return(get_stops(apiURL, agency, attempts + 1))

    except urllib2.URLError:
        return False, "Timeout when opening:  " + base + query

    try:
        data = json.loads(response)
    except ValueError:
        return False, 'NO JSON Data in get_stops: ' + base + query
    except:
        return False, 'UNKNOWN ERROR in get_stops' + base + query

    try:
        stops = data['data']['list']
    except KeyError:
        return False, 'Stops list not formatted as expected: ' + base + query

    return True, stops


def check_arrivals(apiURL, stop, arr, attempts=0):

    base = apiURL + '/api/where/arrivals-and-departures-for-stop/' + stop + '.json?'

    # Checks arrivals and departures for a stop that occur only in the next 10 minutes because we don't really care about buses from the past or too far into the future.
    query = urllib.urlencode(dict(key=API_KEY,
                                  minutesAfter='10',
                                  minutesBefore='0'))

    try:
        response = urllib.urlopen(base + query).read()
    except IOError:
        if attempts > 3:
            return False, 'Unable to open:  ' + base + query
        else:
            time.sleep(20)
            # print 'check_arrivals sleeping'
            return(check_arrivals(apiURL, stop, arr, attempts + 1))

    except urllib2.URLError:
        return False, "Timeout when opening:  " + base + query

    try:
        data = json.loads(response)
    except ValueError:
        return False, 'NO JSON Data in get_stops: ' + base + query
    except:
        return False, 'UNKNOWN ERROR in get_stops' + base + query

    try:
        arrivals = data['data']['entry']['arrivalsAndDepartures']
    except KeyError:
        return False, 'Arrivals list not formatted as expected: ' + base + query

    for arrival in arrivals:
        # Check for number of predicted vs. scheduled arrivals
        if arrival['predicted']:
            arr['predicted'] += 1

            # Check for number of "perfect" predictions, i.e., predicted equals scheduled
            if arrival['predictedArrivalTime'] == arrival['scheduledArrivalTime']:
                arr['perfect'] += 1
        else:
            arr['scheduled'] += 1
    return True, ""


def check_for_resolution(code, description):
    # Check the OBA email to see if this code has been resolved.
    # If it has, clear the alert and send an email to everyone on the Alert list.

    today = datetime.datetime.today()
    cutoff = today - datetime.timedelta(days=1)

    # Connect, login and select the INBOX
    server = imaplib.IMAP4_SSL(IMAP_HOST)
    server.login(USERNAME, PASSWORD)
    server.list()
    # Out: list of "folders" aka labels in gmail.
    server.select("inbox")  # connect to inbox

    # Search for relevant messages
    # see http://tools.ietf.org/html/rfc3501#section-6.4.5
    result, data = server.search(None, '(SINCE %s)' % cutoff.strftime('%d-%b-%Y'))

    ids = data[0]  # data is a list.
    id_list = ids.split()  # ids is a space separated string

    resolved = False

    for email_id in id_list:
        result, data = server.fetch(email_id, '(RFC822)')

        msg = email.message_from_string(data[0][1])

        # Pulls the body of the solution email.
        body = ''
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                body += str(part.get_payload()) + '\n'

        if msg['Subject'].find("Re: OBA Alert!: {0}.".format(code)) > -1:
            resolved = True
            resolver = msg['From']
            time_resolved = msg['date']
            break

    if resolved:
        clear_alert(code, description)
        resolution_msg_template = "OBA Alert: {0}, {1} \nwas resolved by {2} at {3}.\n\nSOLUTION:  {4}"
        send_gmail(ALERT_LIST,
                   resolution_msg_template.format(code,
                                                  description,
                                                  resolver,
                                                  time_resolved,
                                                  body),
                   "OBA Alert Resolved!: {0}.".format(code))
        return True
    else:
        return False


def send_gmail(recipients, message, subject):

    msg = MIMEMultipart()
    msg["From"] = FROM_ADDRESS
    msg["Subject"] = subject
    msg['Date'] = formatdate(localtime=True)
    message1 = MIMEText(message, 'plain')
    msg.attach(message1)

    # The actual mail send
    server = smtplib.SMTP(SMTP_HOST)
    server.starttls()
    server.login(USERNAME, PASSWORD)
    server.sendmail(FROM_ADDRESS, recipients, msg.as_string())
    server.close()


def clear_alert(code, description):

    # Update the status code in the alert_status.csv file
    status_file = open(CSV_STATUS_FILE, 'wb')
    status_array = []
    status_array.append({'status': 0, 'code': code, 'description': description})
    fieldnames = ['status', 'code', 'description']
    writer = csv.DictWriter(status_file, delimiter=',', fieldnames=fieldnames)
    writer.writerow(dict((fn, fn) for fn in fieldnames))
    for row in status_array:
        writer.writerow(row)


def create_alert(description):

    # Get the previous code
    status, code, existing_description = get_alert_status()
    code += 1

    # Send the relevant emails and texts
    send_gmail(ALERT_LIST, description, "OBA Alert!: " + str(code) + '.')

    # Update the status code in the alert_status.csv file
    status_file = open(CSV_STATUS_FILE, 'wb')
    status_array = [{'status': 1, 'code': code, 'description': description}]
    fieldnames = ['status', 'code', 'description']
    writer = csv.DictWriter(status_file, delimiter=',', fieldnames=fieldnames)
    writer.writerow(dict((fn, fn) for fn in fieldnames))
    for row in status_array:
        writer.writerow(row)


def get_alert_status():
    """
    get_alert_status checks a file called alert_status.csv.
    If the status of the file is a 1, then the system is in alert status waiting for a response
    If the status of this file is a 0, then the system is operating normally
    """

    if os.path.exists(CSV_STATUS_FILE):
        status_file = open(CSV_STATUS_FILE)
        reader = csv.DictReader(status_file)
        for row in reader:
            return int(row['status']), int(row['code']), row['description']
    else:
        return 0, 0, None


def main():
    '''Check to see if an alert has already been sent but not addressed.
      This will prevent duplcate alerts'''

    status, code, description = get_alert_status()

    now = datetime.datetime.now()
    seconds_after_midnight = now.hour * 3600 + now.minute * 60 + now.second
    cur_hour = now.hour
    cur_day_of_week = now.weekday()

    if status:
        resolved = check_for_resolution(code, description)
        if not resolved:
            return
    elif DAYS_OF_WEEK_TO_REPORT[cur_day_of_week] == 0:
        # don't send reports on disabled days of week
        return
    elif seconds_after_midnight < START_OF_DAY:
        return
    elif seconds_after_midnight > END_OF_DAY:
        return
    elif cur_hour in REPORT_HOURS:
        # find the last hour a report was sent
        if os.path.exists(REPORT_STATUS_FILE):
            with open(REPORT_STATUS_FILE) as f:
                last_hour_sent = int(f.read())
        else:
            last_hour_sent = -1
        if last_hour_sent == cur_hour:
            return
        else:
            # write last hour
            with open(REPORT_STATUS_FILE, 'wb') as f:
                f.write(str(cur_hour))
    else:
        return

    result, agencies = get_agencies(ROOT_URL)
    if not result:
        create_alert('Problem getting agencies.  {0}'.format(agencies))
        return

    report = ""

    for agency in agencies:

        result, stops = get_stops(ROOT_URL, agency)
        if not result:
            report = stops
            create_alert(report)
            continue

        lim = len(stops) * PCT_STOPS
        stopIndex = 0
        counts = dict(predicted=0,
                      scheduled=0,
                      perfect=0)

        for stop in stops:

            stopIndex += 1
            result, message = check_arrivals(ROOT_URL, stop, counts)
            if not result:
                report = message
                create_alert(report)
                break
            if stopIndex > lim:
                break

        # These are sanity checks for the various agencies.  
        # They will only be run if the agency ID is in the realtime_agencies list
        if not(agency['agencyId'] in REALTIME_AGENCIES):
            pass
            # print agency['agencyId'] + " is not included in the realtime test."
        elif counts['predicted'] < counts['scheduled']:
            create_alert(agency['agencyId'] + " has < 50% predicted arrivals at select stops.")
        elif counts['predicted'] + counts['scheduled'] == 0:
            create_alert(agency['agencyId'] + " is not returning any schedule or predicted times!")
        elif float(counts['perfect']) / float(counts['predicted']) > .9:
            create_alert(agency['agencyId'] + " is reporting > 90% perfect predictions.")
        else:
            # print agency['agencyId'] + " is looking good."
            pass

        for s in ["\n\n" + agency['agencyId'],
                  "\n\nTrips with real-time: " + str(counts['predicted']),
                  " of " + str(counts['scheduled'] + counts['predicted']),
                  "\nTrips without real-time: " + str(counts['scheduled']),
                  " of " + str(counts['scheduled'] + counts['predicted']),
                  "\nPerfect predictions: " + str(counts['perfect']),
                  " of " + str(counts['scheduled'] + counts['predicted'])]:
            report += s

    send_gmail(REPORT_LIST, report, 'OBA Report')

if __name__ == '__main__':
    main()
