from typing import List

import dash
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
import plotly.graph_objs as go
from flask_caching import Cache
import os

import flask
import pandas as pd
import logging as log
from timeloop import Timeloop
from datetime import datetime, timedelta
from glob import glob

EXTERNAL_STYLESHEETS = [
    'https://codepen.io/chriddyp/pen/bWLwgP.css'
]

DATA_CSV_URL = 'https://docs.google.com/spreadsheets/d/1D6okqtBS3S2NRC7GFVHzaZ67DuTw7LX49-fqSLwJyeo/export?format=csv'
DATA_LINK_URL = 'https://docs.google.com/spreadsheets/d/1D6okqtBS3S2NRC7GFVHzaZ67DuTw7LX49-fqSLwJyeo'
DATA_FETCH_INTERVAL = timedelta(minutes=10)
DATE_COL = 'date_report'
PROVINCE_COL = 'province'
REGION_COL = 'health_region'
REQUIRED_COLS = {DATE_COL, PROVINCE_COL, REGION_COL}
NONE_OPTION = dict(label=None, value=None)
DATA_DIR = './data'

log.basicConfig(level=log.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
timeloop = Timeloop()

latest_df = None

server = flask.Flask('app')

cache = Cache(app=server, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 0
})

app = dash.Dash(
    'app',
    server=server,
    external_stylesheets=EXTERNAL_STYLESHEETS)

app.layout = html.Div([
    html.Div([
        html.Div([html.H1('C19 Canada', id='title')], className='ten columns'),
        html.Div([html.Button('Reload Page', id='reload-button')], className='two columns')
    ], className='row'),
    html.Div([
        html.Div([
            html.A('Data source', href=DATA_LINK_URL),
            html.P(id='last-fetched')]),
    ], className='row'),
    html.Div([
        html.Div([
            html.P('Province'),
            dcc.Dropdown(id='province-dropdown', options=[], value=None),
        ])
    ], className='row'),
    html.Div([
        html.Div([
            html.P('Region'),
            dcc.Dropdown(id='region-dropdown', options=[], value=None),
        ])
    ], className='row'),
    html.Div([
        html.Div([
            dcc.Loading([dcc.Graph(id='cumulative-cases', style={'height': 'auto'})]),
        ], className='twelve columns'),
    ], className='row'),
    html.Div(id='page-loaded'),
], className="container")


@timeloop.job(interval=DATA_FETCH_INTERVAL)
def fetch_data():
    df = pd.read_csv(DATA_CSV_URL, skiprows=2)
    assert (REQUIRED_COLS <= set(df.columns))
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], format='%d-%m-%Y')
    filename = os.path.join(DATA_DIR, 'c19 {}.csv'.format(datetime.now().strftime('%Y-%m-%d %H-%M-%S')))
    df.to_csv(filename)
    log.info('Fetched {} rows'.format(len(df.index)))
    global latest_df
    latest_df = None
    cache.clear()


def stored_data_files() -> List[str]:
    return sorted(glob(os.path.join(DATA_DIR, '*.csv')))


def get_df() -> pd.DataFrame:
    global latest_df
    if latest_df is None:
        latest_file = stored_data_files()[0]
        latest_df = pd.read_csv(latest_file)
    return latest_df


def build_options(items: List[str]) -> List[dict]:
    return [dict(label=opt, value=opt) for opt in sorted(list(set(items)))]


@app.callback([Output('last-fetched', 'children')],
              [Input('reload-button', 'n_clicks')])
def foo(_):
    last_mtime = datetime.fromtimestamp(os.path.getmtime(stored_data_files()[0]))
    return ['(last fetched {} PST)'.format(last_mtime.strftime('%Y-%m-%d %H-%M-%S'))]


@app.callback([Output('province-dropdown', 'options')],
              [Input('reload-button', 'n_clicks')])
@cache.cached()
def foo(_):
    return [build_options(get_df()[PROVINCE_COL].values)]


@app.callback([Output('region-dropdown', 'options'), Output('region-dropdown', 'value')],
              [Input('province-dropdown', 'value')])
@cache.memoize()
def foo(province: str):
    return [build_options(filtered_df(province=province)[REGION_COL].values), None]


@cache.memoize()
def filtered_df(province: str = None, region: str = None) -> pd.DataFrame:
    df = get_df()
    if province is not None:
        df = df[df[PROVINCE_COL] == province]
    if region is not None:
        df = df[df[REGION_COL] == region]
    return df


@app.callback([Output('cumulative-cases', 'figure')],
              [Input('reload-button', 'n_clicks'),
               Input('province-dropdown', 'value'),
               Input('region-dropdown', 'value')])
def foo(_, province: str, region: str):
    df = filtered_df(province=province, region=region)
    return [
        px.histogram(df, x=DATE_COL, cumulative=True, title='Cumulative Cases')
    ]


if not stored_data_files():
    fetch_data()

app = server

if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=True, port=80)
