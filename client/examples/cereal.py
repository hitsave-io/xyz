import csv
import requests
from hitsave import experiment


@experiment
def cereals():
    response = requests.get("https://docs.dagster.io/assets/cereal.csv")
    lines = response.text.split("\n")
    cereal_rows = [row for row in csv.DictReader(lines)]

    return cereal_rows


@experiment
def filter_cereals(v):
    """Cereals manufactured by Nabisco"""
    return [row for row in cereals() if row["mfr"] == v]


nc = filter_cereals("N")
kc = filter_cereals("N")
print(nc)
