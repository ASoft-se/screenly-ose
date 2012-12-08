# -*- coding: utf8 -*-

__author__ = "Viktor Petersson, Christian Nilsson"
__copyright__ = "Copyright 2012, WireLoad Inc"
__license__ = "Dual License: GPLv2 and Commercial License"
__version__ = "0.1"
__email__ = "vpetersson@wireload.net"

import ConfigParser
from os import path, makedirs, getenv
from datetime import datetime
from netifaces import ifaddresses
import sqlite3

def logg(string, out=None):
    if out is None:
        print string
    else:
        out(string)

class Config:
    """Handle all configuration parameters for screenly"""

    def __init__(self, debug_out=None):
        # Get config file
        config = ConfigParser.ConfigParser({'listen':'0.0.0.0','port':'8080','resolution':'1920x1080'})
        conf_file = path.join(getenv('HOME'), '.screenly', 'screenly.conf')
        if not path.isfile(conf_file):
            raise Exception('Config-file %s missing.' % conf_file)
        logg('Reading config-file...', debug_out)
        config.read(conf_file)

        # Get main config values
        self.database = path.join(getenv('HOME'), config.get('main', 'database'))
        self.nodetype = config.get('main', 'nodetype')
        self.listen = config.get('main', 'listen')
        self.port = config.getint('main', 'port')

        # Get server config values
        self.configdir = path.join(getenv('HOME'), config.get('main', 'configdir'))

        # Get viewer config values
        self.show_splash = config.getboolean('viewer', 'show_splash')
        self.audio_output = config.get('viewer', 'audio_output')
        self.shuffle_playlist = config.getboolean('viewer', 'shuffle_playlist')
        self.resolution = config.get('viewer', 'resolution')

    def time_lookup(self):
        if self.nodetype == "standalone":
            return datetime.now()
        elif self.nodetype == "managed":
            return datetime.utcnow()

    def get_conf_url(self):
        try:
            if self.listen == '0.0.0.0':
                server = ifaddresses('eth0')[2][0]['addr']
            else:
                server = self.listen
            return 'http://%s:%i' % (server, self.port)
        except:
            return None

    def get_viewer_baseurl(self):
        if self.listen == '0.0.0.0':
            server = '127.0.0.1'
        else:
            server = self.listen
        return 'http://%s:%i' % (server, self.port)


    def initiate_db(self):
        # Create config dir if it doesn't exist
        if not path.isdir(self.configdir):
            makedirs(self.configdir)

        conn = self.get_sqlconn()
        c = conn.cursor()

        # Check if the asset-table exist. If it doesn't, create it.
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assets'")
        asset_table = c.fetchone()

        if not asset_table:
            c.execute("CREATE TABLE assets (asset_id TEXT PRIMARY KEY, name TEXT, uri TEXT, start_date TIMESTAMP, end_date TIMESTAMP, duration TEXT, mimetype TEXT)")
        conn.close()

    def get_sqlconn(self):
        return sqlite3.connect(self.database, detect_types=sqlite3.PARSE_DECLTYPES)

    def sqlfetch(self, sql, parameters={}, do_fetchone=False):
        conn = self.get_sqlconn()
        c = conn.cursor()
        c.execute(sql, parameters)
        if do_fetchone:
            result = c.fetchone()
        else:
            result = c.fetchall()
        conn.close()
        return result

    def sqlcommit(self, sql, parameters={}):
        conn = self.get_sqlconn()
        c = conn.cursor()
        c.execute(sql, parameters)
        conn.commit()
        conn.close()
