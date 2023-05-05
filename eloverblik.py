# %%
# https://api.eloverblik.dk/CustomerApi/swagger/index.html

import requests
import json
import numpy as np
import pandas as pd
from datetime import timedelta
from datetime import datetime as dt

def getData(token, startDate, endDate):

    # Get data access token for subsequent requests
    get_data_access_token_url = 'https://api.eloverblik.dk/CustomerApi/api/token'
    headers = {
        'accept': 'application/json',
        'Authorization': 'Bearer ' + token,
    }

    response = requests.get(get_data_access_token_url, headers=headers)
    data_access_token = response.json()['result']

    # Get id of first meter - edit if you have more than one meter
    metering_points_url = 'https://api.eloverblik.dk/CustomerApi/api/meteringpoints/meteringpoints'
    headers = {
        'accept': 'application/json',
        'Authorization': 'Bearer ' + data_access_token,
    }
    meters = requests.get(metering_points_url, headers=headers)
    if(meters.ok == False): 
        print('Eloverblik is currently having issues: ' + meters.reason)
        return None

    first_meter = meters.json()['result'][0]['meteringPointId']

    meter_json = {
        "meteringPoints": {
            "meteringPoint": [
                first_meter
            ]
        }
    }

    # Charges
    charges_data = 'https://api.eloverblik.dk/CustomerApi/api/meteringpoints/meteringpoint/getcharges'
    charges_data_request = requests.post(
        charges_data, headers=headers, json=meter_json)
    data = json.loads(charges_data_request.text)


    # Tariff
    positions = [tariff['position'] for tariff in [item['prices']
                            for item in data['result'][0]['result']['tariffs']][0]]

    prices = [tariff['price'] for tariff in [item['prices']
    for item in data['result'][0]['result']['tariffs']][0]]

    df = pd.DataFrame({"Position": positions, "Price": prices})

    filter = '{"PriceArea":["DK1"]}'
    sort = "HourUTC ASC"
    url = f"https://api.energidataservice.dk/dataset/Elspotprices?offset=0&start={startDate.strftime('%Y/%m/%dT%H:%M').replace('/','-')}&end={endDate.strftime('%Y/%m/%dT%H:%M').replace('/','-')}&filter={filter}&sort={sort}&timezone=UTC"
    spot_price_res = requests.get(url)

    data = json.loads(spot_price_res.text)
    dfSpot = pd.DataFrame({'HourUTC': [item['HourUTC'] for item in data['records']], 'Spot_Price':  [
                        item['SpotPriceDKK'] for item in data['records']]})

    for row in dfSpot['HourUTC']:
        pos_number = row.split('T')[1].split(':')[0]
        #print(pos_number)
        if (pos_number.startswith('0')):
            pos_number = pos_number[1:]
        #print(pos_number)
        time_stamp = row.split('T')[1]

        # print(time_stamp)
        dfSpot.loc[dfSpot['HourUTC'].str.endswith(time_stamp), 'Tariff'] = df.query(
            f'Position=="{str(int(pos_number)+1)}"')['Price'].item()

    #print(df.query('Position=="18"')['Price'].item())
    dfSpot['Spot_Price'] = np.round((dfSpot['Spot_Price'] / 1000),2)
    transmissionnettarif = 0.073
    systemtarif = 0.068
    elafgift = 0.010
    dfSpot['Total_Price'] = np.round((dfSpot['Spot_Price'] + (dfSpot['Tariff']) + (transmissionnettarif + systemtarif + elafgift)) * 1.25,2)
    dfSpot['HourUTC'] = pd.to_datetime(dfSpot['HourUTC'], utc=True)
    return dfSpot

