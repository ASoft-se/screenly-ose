#!/usr/bin/env python
# -*- coding: utf8 -*-

__author__ = "Viktor Petersson"
__copyright__ = "Copyright 2012, WireLoad Inc"
__license__ = "Dual License: GPLv2 and Commercial License"
__version__ = "0.1.2"
__email__ = "vpetersson@wireload.net"

from Config import Config
from sys import platform, stdout
from requests import get as req_get, head as req_head
from os import path, getloadavg, statvfs
from hashlib import md5
from json import dumps, loads 
from datetime import datetime, timedelta
from bottle import route, run, debug, template, request, validate, error, static_file, get
from dateutils import datestring
from StringIO import StringIO
from PIL import Image
from urlparse import urlparse
from hurry.filesize import size
from subprocess import check_output

# Get config
config = Config()

def get_playlist():
    
    assets = config.sqlfetch("SELECT asset_id, name, uri, start_date, end_date, duration, mimetype FROM assets ORDER BY name")
    
    playlist = []
    for asset in assets:
        # Match variables with database
        asset_id = asset[0]  
        name = asset[1]
        uri = asset[2] # Path in local database
        input_start_date = asset[3]
        input_end_date = asset[4]

        try:
            start_date = datestring.date_to_string(asset[3])
        except:
            start_date = None

        try:
            end_date = datestring.date_to_string(asset[4])
        except:
            end_date = None
            
        duration = asset[5]
        mimetype = asset[6]

        playlistitem = {
                "name" : name,
                "uri" : uri,
                "duration" : duration,
                "mimetype" : mimetype,
                "asset_id" : asset_id,
                "start_date" : start_date,
                "end_date" : end_date
                }
        if (start_date and end_date) and (input_start_date < config.time_lookup() and input_end_date > config.time_lookup()):
            playlist.append(playlistitem)
    
    return dumps(playlist)

def get_assets():
    
    assets = config.sqlfetch("SELECT asset_id, name, uri, start_date, end_date, duration, mimetype FROM assets ORDER BY name")
    
    playlist = []
    for asset in assets:
        # Match variables with database
        asset_id = asset[0]  
        name = asset[1]
        uri = asset[2] # Path in local database

        try:
            start_date = datestring.date_to_string(asset[3])
        except:
            start_date = ""

        try:
            end_date = datestring.date_to_string(asset[4])
        except:
            end_date = ""
            
        duration = asset[5]
        mimetype = asset[6]

        playlistitem = {
                "name" : name,
                "uri" : uri,
                "duration" : duration,
                "mimetype" : mimetype,
                "asset_id" : asset_id,
                "start_date" : start_date,
                "end_date" : end_date
                }
        playlist.append(playlistitem)
    
    return dumps(playlist)

@route('/process_asset', method='POST')
def process_asset():

    if (request.POST.get('name','').strip() and 
        request.POST.get('uri','').strip() and
        request.POST.get('mimetype','').strip()
        ):

        name =  request.POST.get('name','').decode('UTF-8')
        uri = request.POST.get('uri','').strip()
        mimetype = request.POST.get('mimetype','').strip()

        # Make sure it's a valid resource
        uri_check = urlparse(uri)
        if not (uri_check.scheme == "http" or uri_check.scheme == "https"):
            header = "Ops!"
            message = "URL must be HTTP or HTTPS."
            return template('message', header=header, message=message)

        if "image" in mimetype:
            file = req_get(uri)
        else:
            file = req_head(uri)

        # Only proceed if fetch was successful. 
        if file.status_code == 200:
            asset_id = md5(name+uri).hexdigest()
            
            strict_uri = uri_check.scheme + "://" + uri_check.netloc + uri_check.path

            if "image" in mimetype:
                resolution = Image.open(StringIO(file.content)).size
            else:
                resolution = "N/A"

            if "video" in mimetype:
                duration = "N/A"

            start_date = ""
            end_date = ""
            duration = ""
            
            config.sqlcommit("INSERT INTO assets (asset_id, name, uri, start_date, end_date, duration, mimetype) VALUES (?,?,?,?,?,?,?)", (asset_id, name, uri, start_date, end_date, duration, mimetype))
            
            header = "Yay!"
            message =  "Added asset (" + asset_id + ") to the database."
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

        start_date = datetime.strptime(input_start, '%Y-%m-%d @ %H:%M')
        end_date = datetime.strptime(input_end, '%Y-%m-%d @ %H:%M')

        conn = config.get_sqlconn()
        c = conn.cursor()
        c.execute("SELECT mimetype FROM assets WHERE asset_id=?", (asset_id,))
        asset_mimetype = c.fetchone()
        
        if "image" or "web" in asset_mimetype:
            try:
                duration = request.POST.get('duration','').strip()
            except:
                header = "Ops!"
                message = "Duration missing. This is required for images and web-pages."
                return template('message', header=header, message=message)
        else:
            duration = "N/A"

        c.execute("UPDATE assets SET start_date=?, end_date=?, duration=? WHERE asset_id=?", (start_date, end_date, duration, asset_id))
        conn.commit()
        conn.close()
        
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

        asset_id =  request.POST.get('asset_id','').strip()
        name = request.POST.get('name','').decode('UTF-8')
        uri = request.POST.get('uri','').strip()
        mimetype = request.POST.get('mimetype','').strip()

        try:
            duration = request.POST.get('duration','').strip()
        except:
            duration = None

        try:
            input_start = request.POST.get('start','')
            start_date = datetime.strptime(input_start, '%Y-%m-%d @ %H:%M')
        except:
            start_date = None

        try:
            input_end = request.POST.get('end','').strip()
            end_date = datetime.strptime(input_end, '%Y-%m-%d @ %H:%M')
        except:
            end_date = None

        config.sqlcommit("UPDATE assets SET start_date=?, end_date=?, duration=?, name=?, uri=?, duration=?, mimetype=? WHERE asset_id=?", (start_date, end_date, duration, name, uri, duration, mimetype, asset_id))

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
        config.sqlcommit("DELETE FROM assets WHERE asset_id=?", (asset_id,))
        
        header = "Success!"
        message = "Deleted asset."
        return template('message', header=header, message=message)
    except:
        header = "Ops!"
        message = "Failed to delete asset."
        return template('message', header=header, message=message)

@route('/')
def viewIndex():
    config.initiate_db()
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

    # Make sure the database exist and that it is initiated.
    config.initiate_db()

    url = config.get_conf_url();
    ip_lookup = url is not None
    if not ip_lookup:
        url = "Unable to lookup IP from eth0."

    return template('splash_page', ip_lookup=ip_lookup, url=url)


@route('/view_playlist')
def view_node_playlist():

    nodeplaylist = loads(get_playlist())
    
    return template('view_playlist', nodeplaylist=nodeplaylist)

@route('/view_assets')
def view_assets():

    nodeplaylist = loads(get_assets())
    
    return template('view_assets', nodeplaylist=nodeplaylist)


@route('/add_asset')
def add_asset():
    return template('add_asset')


@route('/schedule_asset')
def schedule_asset():

    query = config.sqlfetch("SELECT asset_id, name FROM assets ORDER BY name")
    assets = []
    for asset in query:
        asset_id = asset[0]
        name = asset[1]
        
        assets.append({
            'name' : name,
            'asset_id' : asset_id,
        })

    return template('schedule_asset', assets=assets)
        
@route('/edit_asset/:asset_id')
def edit_asset(asset_id):

    asset = config.sqlfetch("SELECT asset_id, name, uri, start_date, end_date, duration, mimetype FROM assets WHERE asset_id=?", (asset_id,), True)
    
    name = asset[1]
    uri = asset[2]

    if asset[3]:
        start_date = datestring.date_to_string(asset[3])
    else:
        start_date = None

    if asset[4]:
        end_date = datestring.date_to_string(asset[4])
    else:
        end_date = None

    duration = asset[5]
    mimetype = asset[6]

    asset_info = {
            "name" : name,
            "uri" : uri,
            "duration" : duration,
            "mimetype" : mimetype,
            "asset_id" : asset_id,
            "start_date" : start_date,
            "end_date" : end_date
            }
    #return str(asset_info)
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
