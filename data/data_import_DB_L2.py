# Libraries
import dash
from dash.dependencies import Input, Output, State
import dash_html_components as html
import dash_core_components as dcc
import dash_table
from datetime import timedelta
from datetime import datetime, time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import dash_bootstrap_components as dbc
from datetime import timedelta
import sys

# Recall app
from app import app

import pandas as pd
from sqlalchemy import create_engine
from .data_import_DB import credenciales
import os

from flask_caching import Cache


cache = Cache(
    app.server,
    config={
        # try 'filesystem' if you don't want to setup redis
        "CACHE_DIR": "cache",
        "CACHE_TYPE": "filesystem",
        # 'CACHE_REDIS_URL': os.environ.get('REDIS_URL', '')
    },
)


# credenciales = dict(
#     POSTGRES_DB="db_isa",
#     POSTGRES_USER="postgres",
#     POSTGRES_PASSWORD="ninguna.123",
#     POSTGRES_HOST="extended-case-4.crccn2eby4ve.us-east-2.rds.amazonaws.com",
#     POSTGRES_PORT=5432,
# )

# Database information from env variables
DATABASES = {
    "db_isa": {
        "NAME": credenciales.get("POSTGRES_DB"),
        "USER": credenciales.get("POSTGRES_USER"),
        "PASSWORD": credenciales.get("POSTGRES_PASSWORD"),
        "HOST": credenciales.get("POSTGRES_HOST"),
        "PORT": credenciales.get("POSTGRES_PORT"),
    },
}

# choose the database to use
db = DATABASES["db_isa"]

# construct an engine connection string
engine_string = (
    "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}".format(
        user=db["USER"],
        password=db["PASSWORD"],
        host=db["HOST"],
        port=db["PORT"],
        database=db["NAME"],
    )
)

# create sqlalchemy engine
engine = create_engine(engine_string)

lineas_dict = {
    "comuneros": "Comuneros Primavera",
    "cerromatoso": "Cerromatoso Primavera",
    "virginia": "La Virginia San Carlos",
}
lineas_dict_numbers = {
    "comuneros": 1,
    "cerromatoso": 2,
    "virginia": 3,
}


def get_discharges(date_first="2018-04-05", num_days=1, table_id=1):
    df = pd.read_sql_query(
        f"""SELECT * FROM tbl_discharges_{table_id}
                        WHERE date BETWEEN ('{date_first}'::date - interval '{num_days} days') AND ('{date_first}'::date + interval '{num_days} days') """,
        engine,
    )
    return df


@app.callback(
    [
        Output("memory-towers-model", "data"),
    ],
    [
        Input(component_id="power_line_name_model", component_property="value"),
    ],
)
@cache.memoize()
def filter_towers(power_line_name):
    table_id = lineas_dict_numbers[power_line_name]
    towers = pd.read_sql_table(f"tbl_towers_{table_id}", engine)
    return (towers.to_dict("records"),)


@app.callback(
    [
        Output("memory-outages-model", "data"),
        Output("outage_dropdown_model", "options"),
    ],
    [
        Input(component_id="power_line_name_model", component_property="value"),
    ],
)
@cache.memoize()
def filter_outages(power_line_name):
    table_id = lineas_dict_numbers[power_line_name]
    outages = pd.read_sql_table(f"tbl_outages_{table_id}", engine)
    options_dropdown = [
        {
            "label": f"{num+1}: " + outages.loc[i, "date"].strftime("%Y-%m-%d %H-%M"),
            "value": i,
        }
        for num, i in enumerate(outages.index)
    ]
    return outages.to_dict("records"), options_dropdown


@app.callback(
    [
        Output("memory-discharges-model", "data"),
    ],
    [
        Input(component_id="power_line_name_model", component_property="value"),
        Input("outage_dropdown_model", "value"),
    ],
    [State("memory-outages-model", "data")],
)
@cache.memoize()
def filter_discharges(power_line_name, outage_indicator, data_outages):
    print('Se caga aca?')
    outages = pd.DataFrame.from_dict(data_outages)
    table_id = lineas_dict_numbers[power_line_name]
    # outages = pd.read_sql_table(f"tbl_outages_{table_id}", engine)
    outages["date"] = pd.to_datetime(outages["date"])
    outage_date = outages.loc[int(outage_indicator), "date"]
    print("date outage DB", outage_date)
    discharges = get_discharges(date_first=outage_date, num_days=2, table_id=table_id)
    return (discharges.to_dict("records"),)

@app.callback(
    [
        Output("memory-features-model", "data"),
        Output("memory-clusters-model", "data"),
    ],
    [
        Input(component_id="power_line_name_model", component_property="value"),
        Input("outage_dropdown_model", "value"),
        Input("memory-outages-model", "data")
    ],
    # [State("memory-outages-model", "data")],
)
@cache.memoize()
def filter_features(power_line_name, outage_indicator, data_outages):
    outages = pd.DataFrame.from_dict(data_outages)
    table_id = lineas_dict_numbers[power_line_name]
    features_df = pd.read_sql_query(
        f"""SELECT * FROM tbl_features
                        WHERE line = {table_id} """,
        engine
    )
    outages = pd.read_sql_table(f"tbl_outages_{table_id}", engine)
    outages["date"] = pd.to_datetime(outages["date"])
    outage_date = outages.loc[int(outage_indicator), "date"]
    print("Fecha Outage", outage_date)
    
    df_clusters = pd.read_sql_query(
            f"""SELECT * FROM tbl_discharges_by_cluster
                            where date BETWEEN ('{outage_date}'::timestamp - '24 hours'::interval) AND ('{outage_date}'::timestamp - '5 minutes'::interval)""",
            engine,
        )
    return features_df.to_dict("records"), df_clusters.to_dict("records")

# get discharges from last 24 hours realted to specific power line
def discharges_last_24hours(current_date=datetime(2019,11,11), table_id=1):
    #current_time = datetime.now().time()
    current_time = time(2,18,0)
    current_datetime = datetime.combine(current_date, current_time)

    discharges_24hours_df = pd.read_sql_query(f"""SELECT * FROM tbl_discharges_{table_id}
                                                WHERE date BETWEEN ('{current_datetime}'::timestamp - '24 hours'::interval)
                                                AND ('{current_datetime}'::timestamp)"""
                                                ,engine)

    discharges_24hours_df[['longitude','latitude']] = discharges_24hours_df[['longitude','latitude']].apply(pd.to_numeric)
    discharges_24hours_df.drop(columns=['id_discharges'], inplace=True)

    return discharges_24hours_df, current_datetime

# get towers from specific power line
#def get_towers(table_id):
#    towers_df = pd.read_sql_table(f"tbl_towers_{table_id}", engine)
#    return towers_df