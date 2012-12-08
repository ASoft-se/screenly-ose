#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = "Viktor Petersson"
__copyright__ = "Copyright 2012, WireLoad Inc"
__license__ = "Dual License: GPLv2 and Commercial License"
__version__ = "0.1.2"
__email__ = "vpetersson@wireload.net"

from Config import Config, asset as Asset
from sys import platform, stdout
from requests import head as req_head
from os import path, getloadavg, statvfs
from hashlib import md5
from datetime import datetime, timedelta
from bottle import route, run, debug, template, request, validate, error, static_file, get
from urlparse import urlparse
from hurry.filesize import size
from subprocess import check_output

# Get config
config = Config()

def get_playlist():
    
    assets = config.getassets()
    
    playlist = []
    for asset in assets:
        if (asset.start_date and asset.end_date) and (asset.start_date < config.time_lookup() and asset.end_date > config.time_lookup()):
            playlist.append(asset.playlistitem())
    
    return playlist

def get_assets():
    
    assets = config.getassets()
    
    playlist = []
    for asset in assets:
        playlist.append(asset.playlistitem(""))
    
    return playlist

@route('/process_asset', method='POST')
def process_asset():

    if (request.POST.get('name','').strip() and 
        request.POST.get('uri','').strip() and
        request.POST.get('mimetype','').strip()
        ):

        asset = Asset()
        asset.name =  request.POST.get('name','').decode('UTF-8')
        asset.uri = request.POST.get('uri','').strip()
        asset.mimetype = request.POST.get('mimetype','').strip()

        # Make sure it's a valid resource
        uri_check = urlparse(asset.uri)
        if not (uri_check.scheme == "http" or uri_check.scheme == "https"):
            header = "Ops!"
            message = "URL must be HTTP or HTTPS."
            return template('message', header=header, message=message)

        file = req_head(asset.uri)

        # Only proceed if fetch was successful.
        if file.status_code == 200:
            asset.asset_id = md5(asset.name + asset.uri).hexdigest()

            asset.start_date = ""
            asset.end_date = ""
            asset.duration = ""

            asset.INSERT(config)

            header = "Yay!"
            message =  "Added asset (" + asset.asset_id + ") to the database."
            return template('message', header=header, message=message)
            
        else:
            header = "Ops!"
            message = "Unable to fetch file."
            return template('message', header=header, message=message)
    else:
        header = "Ops!"
        message = "Invalid input."
        return template('message', header=header, message=message)

@route('/process_schedule', method='POST')
def process_schedule():

    if (request.POST.get('asset','').strip() and 
        request.POST.get('start','').strip() and
        request.POST.get('end','').strip()
        ):

        asset_id =  request.POST.get('asset','').strip()
        input_start = request.POST.get('start','').strip()
        input_end = request.POST.get('end','').strip() 

        asset = config.getasset(asset_id)

        asset.start_date = datetime.strptime(input_start, '%Y-%m-%d @ %H:%M')
        asset.end_date = datetime.strptime(input_end, '%Y-%m-%d @ %H:%M')

        if "image" or "web" in asset.mimetype:
            try:
                asset.duration = request.POST.get('duration','').strip()
            except:
                header = "Ops!"
                message = "Duration missing. This is required for images and web-pages."
                return template('message', header=header, message=message)
        else:
            asset.duration = "N/A"

        asset.UPDATE(config)

        header = "Yes!"
        message = "Successfully scheduled asset."
        return template('message', header=header, message=message)
        
    else:
        header = "Ops!"
        message = "Failed to process schedule."
        return template('message', header=header, message=message)

@route('/update_asset', method='POST')
def update_asset():

    if (request.POST.get('asset_id','').strip() and 
        request.POST.get('name','').strip() and
        request.POST.get('uri','').strip() and
        request.POST.get('mimetype','').strip()
        ):

        asset = Asset()
        asset.asset_id =  request.POST.get('asset_id','').strip()
        asset.name = request.POST.get('name','').decode('UTF-8')
        asset.uri = request.POST.get('uri','').strip()
        asset.mimetype = request.POST.get('mimetype','').strip()

        try:
            asset.duration = request.POST.get('duration','').strip()
        except:
            asset.duration = None

        try:
            input_start = request.POST.get('start','')
            asset.start_date = datetime.strptime(input_start, '%Y-%m-%d @ %H:%M')
        except:
            asset.start_date = None

        try:
            input_end = request.POST.get('end','').strip()
            asset.end_date = datetime.strptime(input_end, '%Y-%m-%d @ %H:%M')
        except:
            asset.end_date = None

        asset.UPDATE(config)

        header = "Yes!"
        message = "Successfully updated asset."
        return template('message', header=header, message=message)

    else:
        header = "Ops!"
        message = "Failed to update asset."
        return template('message', header=header, message=message)


@route('/delete_asset/:asset_id')
def delete_asset(asset_id):

    try:
        config.delete_asset(asset_id)

        header = "Success!"
        message = "Deleted asset."
        return template('message', header=header, message=message)
    except Exception as e:
        header = "Ops!"
        message = "Failed to delete asset. %s" % e
        return template('message', header=header, message=message)

@route('/')
def viewIndex():
    return template('index')


@route('/system_info')
def system_info():
    viewer_log_file = '/tmp/screenly_viewer.log'
    if path.exists(viewer_log_file):
        viewlog = check_output(['tail', '-n', '20', viewer_log_file]).split('\n')  
    else:
        viewlog = ["(no viewer log present -- is only the screenly server running?)\n"]

    loadavg = getloadavg()[2]

    resolution = check_output(['tvservice', '-s']).strip()

    # Calculate disk space
    slash = statvfs("/")
    free_space = size(slash.f_bsize * slash.f_bavail)
    
    # Get uptime
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        uptime = str(timedelta(seconds = uptime_seconds))

    return template('system_info', viewlog=viewlog, loadavg=loadavg, free_space=free_space, uptime=uptime, resolution=resolution)

@route('/splash_page')
def splash_page():

    url = config.get_conf_url();
    ip_lookup = url is not None
    if not ip_lookup:
        url = "Unable to lookup IP from eth0."

    return template('splash_page', ip_lookup=ip_lookup, url=url)


@route('/view_playlist')
def view_node_playlist():

    nodeplaylist = get_playlist()
    
    return template('view_playlist', nodeplaylist=nodeplaylist)

@route('/view_assets')
def view_assets():

    nodeplaylist = get_assets()
    
    return template('view_assets', nodeplaylist=nodeplaylist)


@route('/add_asset')
def add_asset():
    return template('add_asset')


@route('/schedule_asset')
def schedule_asset():

    assets = get_assets()

    return template('schedule_asset', assets=assets)
        
@route('/edit_asset/:asset_id')
def edit_asset(asset_id):

    asset_info = config.getasset(asset_id).playlistitem()

    return template('edit_asset', asset_info=asset_info)
        
# Static
@route('/static/:path#.+#', name='static')
def static(path):
    return static_file(path, root='static')

@error(403)
def mistake403(code):
    return 'The parameter you passed has the wrong format!'

@error(404)
def mistake404(code):
    return 'Sorry, this page does not exist!'

#Starting the server listen on configured address and port
run(host=config.listen, port=config.port, reloader=True)
