# %%
import requests
import json
import numpy as np
from datetime import datetime as dt
import pandas as pd
from datetime import timedelta

pd.set_option('mode.chained_assignment', None)

defaultYear = dt.today().year
print('Due to limitations in the Easee API, the period must be scoped to a single month.')
year = input('Enter a year (it will defualt to ' + str(defaultYear) +'): ')
startMonth = int(input('Enter a month (1-12): '))

year = int(year) if year else defaultYear

if(int(year) == dt.today().year and startMonth > dt.today().month):
    print("The input date cannot be bigger than the current month and year")
    exit()

# %%
# Basic setup - Set the period
startDate = dt.today().date().replace(day=1,month=startMonth,year=year)
if(startDate.month == 12):
    endDate = dt.today().date().replace(year=startDate.year+1, month=1, day=1)
else:
    endDate = dt.today().date().replace(month=startDate.month+1, day=1)

def getDateAsString(date):
    return date.strftime("%Y/%m/%d %H:%M:%S").replace('/','-')

# %%
# Login to Easee with credentials to get an Access Token
with open("configuration.json") as file:
    config = json.load(file)
url = "https://api.easee.cloud/api/accounts/login"

payload = {
        "userName": config['Easee']['Username'], 
        "password": config['Easee']['Password']
}

headers = {
    "accept": "application/json",
    "content-type": "application/*+json",
}

response = requests.post(url, json=payload, headers=headers)
token = json.loads(response.text)['accessToken']

# %%
# Fetch Charge Date from the Easee API
url = f"https://api.easee.cloud/api/chargers/lifetime-energy/{config['Easee']['ChargerName']}/hourly?from={getDateAsString(startDate)}&to={getDateAsString(endDate)}"
headers = {
    "accept": "application/json",
    "Authorization": "Bearer " + token
}

response = requests.get(url, headers=headers)
if(not response.ok):
    print('Easee API could not be called: ' + response.reason)
    exit()

resJson = json.loads(response.text)
resWithMeasurements = [x for x in resJson if x['consumption'] > 0]

# [
#  {
#    "year": 2023,
#    "month": 1,
#    "day": 1,
#    "hour": 0,
#    "consumption": 0,
#    "date": "2023-01-01T00:00:00+00:00"
#  },
# }

# %%
# Save all Easee readings into a DateFrame
stringDates = [item['date'] for item in resWithMeasurements]
dates = pd.to_datetime(stringDates, format='%Y-%m-%d %H:%M:%S.%f', utc=True)
dates = dates.tolist()
kWhMeasurements = [item['consumption'] for item in resWithMeasurements]

df = pd.DataFrame({"Dato": pd.to_datetime(dates,utc=True), "KwH": kWhMeasurements})
if(df.empty):
    print('No data could be found from the Easee API')
    exit()


# %%
# Get Tariff data
import eloverblik
dfTotal = eloverblik.getData(config['Eloverblik']['Token'], startDate, endDate)
if(dfTotal is None):
    exit()

# %%

#Merge data based upon the timestamp
merge = pd.merge(df, dfTotal, how='outer', left_on='Dato', right_on='HourDK')

#Only take data where there's a measurement 
mergeRelData = merge[merge['KwH'] > 0]


# Setup variables
mergeRelData['Charge_Price'] = np.round(mergeRelData['KwH'] * mergeRelData['Total_Price'],2)
mergeRelData = mergeRelData.drop(columns=['HourDK'])
mergeRelData['short_date'] = mergeRelData['Dato'].dt.date
mergeRelData['short_date'] = mergeRelData['short_date'].astype('datetime64')

mergeRelData.to_csv('output.csv', index=False) 

# %%
# Display price usage pr. day in the given month

print('_________________________________________________________________')
print('Period: ' + startDate.strftime('%d/%m/%Y') + ' - ' + endDate.strftime('%d/%m/%Y'))
print('Total pris (DKK): ' + str(sum(mergeRelData['Charge_Price'])))
print('Total kWh: ' + str(sum(mergeRelData['KwH'])))
print('Avg DKK/kWh: ' + str(sum( mergeRelData['Charge_Price']/sum(mergeRelData['KwH']))))
print('_________________________________________________________________')
