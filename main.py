# pipenv run uvicorn main:app
from fastapi import FastAPI, Depends, Response, status
from pydantic import BaseModel
from fastapi.responses import FileResponse
import icalendar as ical
from icalendar import vCalAddress, vText
from datetime import datetime, timedelta
from dateutil.parser import parse as dateparse
from dateutil.parser import ParserError
from fastapi.security.api_key import APIKeyHeader
import secrets
import os
import hashlib
import re, json
import sys
import csv
import copy
from io import StringIO
import pytz
from dotenv import load_dotenv
from enum import Enum

load_dotenv()
app = FastAPI()
X_API_KEY = APIKeyHeader(name="X-API-Key")
API_KEY_VALUE = os.getenv('API_KEY')
DOMAIN = os.getenv('DOMAIN')


class Calendar(BaseModel):
    calendar: str
    
    
class Status(Enum):
    CONFIRMED = "Y"
    DECLINED = "N"
    MAYBE = "Maybe"
    NORESPONSE = ""
    
    
class Attendee:
    name: str
    status: Status
    
    def __init__(self, name):
        self.name = name 
        self.status = Status.NORESPONSE


class Event:
    name: str
    start_time: datetime
    end_time: datetime
    location: str = ""
    attendees: list[Attendee]
    
@app.get("/bullet")
def get_calendar_file(response: Response):
    file_path = "Bullet Sailing Schedule.ics"
    response.headers["Cache-Control"] = "no-store"
    
    return FileResponse(
        path=file_path,
        media_type="text/calendar",
        filename="bullet.ics"
    )

@app.post("/update", status_code=204)
async def update(
    data: Calendar,
    response: Response,
    api_key_header: str = Depends(X_API_KEY)
):
    if not isinstance(API_KEY_VALUE, str):
        print("Invalid API KEY set in .env", file=sys.stderr)
        exit(1)

    if not secrets.compare_digest(api_key_header, API_KEY_VALUE):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return "Failure"
            
    csv = csvReader(data.calendar)
    events = parseSchedule(csv)
    createCalendar(events)
    return "Success"
    

def csvReader(fileContents: str):
    f = StringIO(fileContents)
    return csv.reader(f, quotechar='"', delimiter=",")


def parseDate(contents: str):
    # "Sat Jun 14 2025 00:00:00 GMT+1000 (Australian Eastern Standard Time)"
    try:
        # Remove GMT (parser just expects +10)
        contents = contents.replace("GMT", "")
        # Get index of the brackets to strip it
        bi = contents.find("(")
        return dateparse(contents[:bi])
    except ParserError:
        return False


def parseTime(contents: str):
    # "12:30"
    try:    
        return dateparse(contents).time()
    except ParserError:
        return dateparse("12:30pm").time()


def getCrew(row: list[str]):
    crew: list[Attendee] = []
    
    for cell in row[4:13]:
        crew.append(Attendee(cell))
        
    return crew
    

def parseSchedule(reader):
    calendarEvents: list[Event] = []
    crew = None
    
    for row in reader:
        if crew is None:
            crew = getCrew(row)
        date_cell = row[1]
        if (date := parseDate(date_cell)):
            time_cell = row[2]
            date = datetime.combine(date, parseTime(time_cell))

            event = parseEvent(row, date, crew)
            calendarEvents.append(event)

    return calendarEvents


def parseEvent(row: list[str], date: datetime, crew: list[Attendee]) -> Event:
    event = Event()
    
    event.name = row[0]
    event.start_time = date
    event.end_time = date + timedelta(hours=6)
    event.location = """Sandringham Yacht Club
    36 Jetty Rd, Sandringham VIC 3191, Australia"""
    
    people = copy.deepcopy(crew)

    for i, available in enumerate(row[4:4 + len(crew)]):
        people[i].status = Status(available.strip())
        
    event.attendees = people

    return event


def createCalendar(
    events: list[Event],
    name: str = "Bullet Sailing Schedule",
    filter: str | None = None
):

    cal = ical.Calendar()
    cal.add("prodid", f"-//{name}//Calendar//EN")
    cal.add("version", "2.0")

    timezone = pytz.timezone('Australia/Melbourne')

    for race in events:
        event = ical.Event()
        event.add('summary', f"Bullet: {race.name}")
        event.add('dtstart', timezone.localize(race.start_time))
        event.add('dtend', timezone.localize(race.end_time))
        event.add('location', race.location)
        for a in race.attendees:
            # Need to generate a mailto id for each user (even though we don't 
            # have passwords)
            attendee = vCalAddress(f'MAILTO:{hashlib.md5(a.name.encode("utf-8")).hexdigest()}@{DOMAIN}')  
            attendee.params['cn'] = vText(a.name)
            attendee.params['ROLE'] = vText('REQ-PARTICIPANT')
            
            if a.status == Status.CONFIRMED:
                partstat = 'ACCEPTED'
            elif a.status == Status.DECLINED:
                partstat = 'DECLINED'
            else:
                partstat = 'TENTATIVE'
            
            attendee.params['PARTSTAT'] = vText(partstat)
            attendee.params['RSVP'] = vText('FALSE')
            
            event.add('attendee', attendee)
        
        cal.add_component(event)

    with open(f'./{name}.ics', 'wb') as fp:
        fp.write(cal.to_ical())


if __name__ == "__main__":
    filename = "test.csv"

    with open(filename, 'r') as fp:
        data = fp.read()
        # print(data)
        csv = csvReader(data)
        testEvents = parseSchedule(csv)

        for testEvent in testEvents:
            print(f"""
                {testEvent.name}
                {testEvent.start_time}
                {testEvent.end_time}
                {testEvent.location}
                {[a.name for a in testEvent.attendees]}
                {[a.status for a in testEvent.attendees]}
            """)

        createCalendar(testEvents, name="test")
