# %%
# https://api.eloverblik.dk/CustomerApi/swagger/index.html

import requests
import json
import numpy as np
import pandas as pd


def getData(token, startDate, endDate):
    # Get data access token for subsequent requests
    data_access_token = getAccessToken(token)

    # Get id of first meter - edit if you have more than one meter
    metering_points_url = (
        "https://api.eloverblik.dk/CustomerApi/api/meteringpoints/meteringpoints"
    )
    headers = {
        "accept": "application/json",
        "Authorization": "Bearer " + data_access_token,
    }
    meters = requests.get(metering_points_url, headers=headers)
    if meters.ok == False:
        print("Eloverblik is currently having issues: " + meters.reason)
        return None

    first_meter = meters.json()["result"][0]["meteringPointId"]

    meter_json = {"meteringPoints": {"meteringPoint": [first_meter]}}

    # Charges
    charges_data = "https://api.eloverblik.dk/CustomerApi/api/meteringpoints/meteringpoint/getcharges"
    charges_data_request = requests.post(charges_data, headers=headers, json=meter_json)
    data = json.loads(charges_data_request.text)

    # Tariff
    transmissionnettarif = 0
    systemtarif = 0
    elafgift = 0
    discount = 0

    # Fixed costs
    transmissionnettarif, systemtarif, elafgift, discount = getTarifssAndFixedCosts(
        data
    )

    positions = [
        tariff["position"]
        for tariff in [
            item["prices"] for item in data["result"][0]["result"]["tariffs"]
        ][0]
    ]

    prices = [
        tariff["price"]
        for tariff in [
            item["prices"] for item in data["result"][0]["result"]["tariffs"]
        ][0]
    ]

    df = pd.DataFrame({"Position": positions, "Price": prices})

    spotPricing = getPricing(startDate, endDate)
    dfSpot = pd.DataFrame(
        {
            "HourUTC": [item["HourUTC"] for item in spotPricing["records"]],
            "Spot_Price": [item["SpotPriceDKK"] for item in spotPricing["records"]],
        }
    )

    convertDateStringsToDates(df, dfSpot)

    # print(df.query('Position=="18"')['Price'].item())
    dfSpot["Spot_Price"] = np.round((dfSpot["Spot_Price"] / 1000), 2)
    dfSpot["Total_Price"] = np.round(
        (
            dfSpot["Spot_Price"]
            + (dfSpot["Tariff"])
            + (transmissionnettarif + systemtarif + elafgift + discount)
        )
        * 1.25,
        2,
    )
    dfSpot["HourUTC"] = pd.to_datetime(dfSpot["HourUTC"], utc=True)
    return dfSpot


def getTarifssAndFixedCosts(data):
    for tariff in data["result"][0]["result"]["tariffs"]:
        if tariff["name"] == "Transmissions nettarif":
            transmissionnettarif = tariff["prices"][0]["price"]
        if tariff["name"] == "Systemtarif":
            systemtarif = tariff["prices"][0]["price"]
        if tariff["name"] == "Elafgift":
            elafgift = tariff["prices"][0]["price"]
        if tariff["name"] == "Rabat på nettarif N1 A/S":
            discount = tariff["prices"][0]["price"]
    return (
        transmissionnettarif if transmissionnettarif is not None else 0,
        systemtarif if systemtarif is not None else 0,
        elafgift if elafgift is not None else 0,
        discount if discount is not None else 0,
    )


def convertDateStringsToDates(df, dfSpot):
    for row in dfSpot["HourUTC"]:
        pos_number = row.split("T")[1].split(":")[0]
        # print(pos_number)
        if pos_number.startswith("0"):
            pos_number = pos_number[1:]
        # print(pos_number)
        time_stamp = row.split("T")[1]

        # print(time_stamp)
        dfSpot.loc[dfSpot["HourUTC"].str.endswith(time_stamp), "Tariff"] = df.query(
            f'Position=="{str(int(pos_number)+1)}"'
        )["Price"].item()


def getPricing(startDate, endDate):
    filter = '{"PriceArea":["DK1"]}'
    sort = "HourUTC ASC"
    url = f"https://api.energidataservice.dk/dataset/Elspotprices?offset=0&start={startDate.strftime('%Y/%m/%dT%H:%M').replace('/','-')}&end={endDate.strftime('%Y/%m/%dT%H:%M').replace('/','-')}&filter={filter}&sort={sort}&timezone=UTC"
    spot_price_res = requests.get(url)

    data = json.loads(spot_price_res.text)
    return data


def getAccessToken(token):
    get_data_access_token_url = "https://api.eloverblik.dk/CustomerApi/api/token"
    headers = {
        "accept": "application/json",
        "Authorization": "Bearer " + token,
    }

    response = requests.get(get_data_access_token_url, headers=headers)
    data_access_token = response.json()["result"]
    return data_access_token
