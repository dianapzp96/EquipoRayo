import lib.st_dbscan_model as st_dbscan_model
import lib.features as features
import lib.svm_predictor as svm_predictor
import data.data_import_DB_L2 as di_db_2
import data.data_import_DB as di_db
import pandas as pd
from dash.exceptions import PreventUpdate
import json
from lib import buffer
import os
from datetime import datetime as dt
from dash_table.Format import Format, Group, Scheme, Symbol
import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from dash_html_components import Div
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# Recall app
import data.data_import_DB_L2

from app import app
from dash.dependencies import ClientsideFunction, Input, Output, State
import dash_table
import lib.buffer as buf

from flask_caching import Cache

from lib.stats import mapbox_token
from lib.stats import mapstyle
import lib.buffer as buffer

#time libraries
from timeit import default_timer as timer

start_abs = timer()

## INITIALIZATION

# initialize ST-DBSCAN parameters
eps1_km = 10  # spatial distance of 10 km
eps2 = 10  # temporal distance of 10 min
min_samples = 5  # min number of dicharges in cluster nuclei
km_per_radian = 6371.0088
eps1 = eps1_km / km_per_radian

# define predictor path
predictor_path = r'./predictor/'
pkl_filename = 'SVM_model.pkl'

for line in range(1,4):

    ## DATA COLLECTION AND FILTERING
    start = timer()
    # get discharges and filter by time (last 24 hours)
    discharges_df, current_datetime = di_db_2.discharges_last_24hours(table_id=line)#CHANGE FUNC

    if not discharges_df.empty:
        # get towers from DB
        exec(f"towers_df = di_db.towers_{line}")

        # filter discharges within buffer area
        x_buffer, y_buffer, buffer_dist = buffer.buffer_line(distance=30
                                                            ,towers_buffer=towers_df)
        discharges_gdf = features.convertir_gdf(discharges_df)
        discharges_df = discharges_gdf.loc[discharges_gdf.within(buffer_dist.geometry.iloc[0])]
        
        end = timer()
        print('data collection line {}: {}'.format(line, end-start))

        if not discharges_df.empty:

            ## CLUSTERING
            start = timer()
            # prepare discharges to be enter to ST-DBSCAN algorithm
            data_array = st_dbscan_model.data_preparation(discharges_df=discharges_df
                                                        ,current_datetime=current_datetime)
            # ST-DBSCAN algorithm
            labels = st_dbscan_model.st_dbscan(eps1=eps1
                                            ,eps2=eps2
                                            ,min_samples=min_samples
                                            ,data_array=data_array)

            # construct dataframe using ST-DBSCAN output
            discharges_by_cluster_df = st_dbscan_model.discharges_by_cluster(data_array=data_array
                                                                            ,labels=labels
                                                                            ,discharges_df=discharges_df)

            end = timer()
            print('clustering line {}: {}'.format(line, end-start))

            ## FEATURIZATION
            start = timer()
            # construct features
            clean_features_df = features.extract_features(df_discharges=discharges_by_cluster_df
                                                        ,df_towers=towers_df)

            # clean noise and poor clusters of features dataframe
            #clean_features_df = features.clean_features(raw_features_df=raw_features_df)

            end = timer()
            print('featurization line {}: {}'.format(line, end-start))

            ## PREDICTION
            start = timer()
            # perform SVM prediction
            prediction = svm_predictor.predict_outage(path=predictor_path
                                                    ,pkl_filename=pkl_filename
                                                    ,clean_features_df=clean_features_df)

            # create and filter dataframe from prediction output
            filter_prediction_df = svm_predictor.create_prediction_df(clean_features_df=clean_features_df
                                                            ,prediction=prediction
                                                            ,threshold=0.3)

            end = timer()
            print('prediction line {}: {}'.format(line, end-start))

            # get discharges belonging to filtered clusters
            clusters_prediction_index = filter_prediction_df.index
            exec(f"discharges_by_cluster_prediction_{line} = discharges_by_cluster_df[discharges_by_cluster_df.cluster.isin(clusters_prediction_index)]")
            #exec(f"print(discharges_by_cluster_prediction_{line})")

end_abs = timer()
print('Total: {}'.format(end_abs - start_abs))

def get_realtime_figure(df_clusters=discharges_by_cluster_df_temp
#                        ,towers=towers_df
#                        ,df_features=filter_prediction_df,
#                        ):
#                        df_clusters.cluster = pd.Categorical(df_clusters.cluster)
#                        map_fig = px.scatter_mapbox(
#                            df_clusters,
#                            lat="latitude",
#                            lon="longitude",
#                            color="cluster",
#                            hover_data=["time_delta", "date"],
#                        )
#
#                        map_fig.add_trace(
#                            go.Scattermapbox(
#                                lat=towers.latitude,
#                                lon=towers.longitude,
#                                mode="markers",  # markers+lines
#                                marker=go.scattermapbox.Marker(size=7, color="black", opacity=0.7),
#                                name="Towers",
#                                hovertemplate="longitude: %{lon:.2f}<br>" + "latitude: %{lat:.2f}<br>",
#                            )
#                        )
#                        lon_x, lon_y, gdf_buffer = buf.buffer_line(10, towers_buffer=towers)
#                        centro = gdf_buffer.centroid
#                        x = centro.x.iloc[0]
#                        y = centro.y.iloc[0]
#                        map_fig.update_layout(
#                            margin={"t": 0.2, "l": 0, "b": 10},
#                            autosize=True,
#                            height=500,
#                            hovermode="closest",
#                            mapbox=dict(
#                                accesstoken=mapbox_token,
#                                style=mapstyle,
#                                center=dict(lat=y, lon=x),
#                                zoom=8,
#                            ),
#                        )
#                        map_fig["layout"]["uirevision"] = "no reset of zoom"
#                        return map_fig


## print('La figura',get_realtime_figure()
#figure = get_realtime_figure()
#

#@app.callback(
#    [
#        Output("cluster-realtime-graph", "figure"),
#        Output("hora", "children"),
#        Output("card-probability", "children"),
#    ],
#    [
#        Input("real-time-interval", "n_intervals"),
#    ],
#)
#def update_graph(num):
#    # print("""update every 3 seconds""")
#    if num == 0:
#        raise PreventUpdate
#    else:
#        return (
#            figure,
#            dt.now().strftime("%H-%M-%S.%f")[:-4],
#            "{:.1f}%".format(filter_prediction_df.prediction.max() * 100),
#        )
