# -*- coding: utf8 -*-

__author__ = "Viktor Petersson, Christian Nilsson"
__copyright__ = "Copyright 2012, WireLoad Inc"
__license__ = "Dual License: GPLv2 and Commercial License"
__version__ = "0.1"
__email__ = "vpetersson@wireload.net"

import ConfigParser
from os import path, makedirs, getenv
from datetime import datetime
from dateutils import datestring
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
        self.configdir = path.join(getenv('HOME'), config.get('main', 'configdir'))
        self.database = path.join(getenv('HOME'), config.get('main', 'database'))
        # Make sure the database exist and that it is initiated.
        self.__init_db(debug_out)
        self.nodetype = config.get('main', 'nodetype')
        self.listen = config.get('main', 'listen')
        self.port = config.getint('main', 'port')

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


    def __init_db(self, debug_out):
        # Create config dir if it doesn't exist
        if not path.isdir(self.configdir):
            makedirs(self.configdir)
        # DB can be located in other then configdir

        conn = self.get_sqlconn()
        c = conn.cursor()

        # Check if the asset-table exist. If it doesn't, create it.
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assets'")
        asset_table = c.fetchone()

	create_table="CREATE TABLE assets (asset_id TEXT PRIMARY KEY, name TEXT, uri TEXT, start_date TIMESTAMP, end_date TIMESTAMP, duration TEXT, mimetype TEXT)"
        if not asset_table:
	    logg('Creating database.', debug_out)
            c.execute(create_table)
        else:
            # Check for need of migration
            try:
                c.execute("SELECT md5 FROM assets")
                table_needs_update = c.fetchone()
            except:
                table_needs_update = False

            # if the column 'md5' exist, drop it. even older column 'filename' is also droped
            if table_needs_update:
	        logg('Update database (drop filename and md5) ...', debug_out)
                # This can fail if there is duplicate of asset_id TODO: tell user to remove them if they exist before migrating
                fields = "asset_id, name, uri, start_date, end_date, duration, mimetype"
                migration= """
                    BEGIN TRANSACTION;
                    CREATE TEMPORARY TABLE assets_backup(""" + fields + """);
                    INSERT INTO assets_backup SELECT """ + fields + """ FROM assets;
                    DROP TABLE assets;
                    """ + create_table + """
                    INSERT INTO assets SELECT """ + fields + """ FROM assets_backup;
                    DROP TABLE assets_backup;
                    COMMIT;
                    """
                try:
                    c.executescript(migration)
                    conn.commit()
	            logg('Database update Done', debug_out)
	        except Exception as e:
	            logg('Database update failed with Exception: %s' % e, debug_out)

        conn.close()

    def get_sqlconn(self):
        return sqlite3.connect(self.database, detect_types=sqlite3.PARSE_DECLTYPES)

    def sqlfetch(self, sql, parameters={}):
        conn = self.get_sqlconn()
        c = conn.cursor()
        c.execute(sql, parameters)
        result = c.fetchall()
        conn.close()
        return result

    def sqlcommit(self, sql, parameters={}):
        conn = self.get_sqlconn()
        c = conn.cursor()
        c.execute(sql, parameters)
        conn.commit()
        conn.close()


    def getassets(self, exsql="ORDER BY name", parameters={}):
        assets = []
        query = self.sqlfetch("SELECT asset_id, name, uri, start_date, end_date, duration, mimetype FROM assets %s" % exsql, parameters)
        for row in query:
            assets.append(asset(row))
        return assets

class asset:
    """asset reuse"""

    def __init__(self, qrow):
        # handle query SELECT as in getassets
        self.asset_id = qrow[0]
        self.name = qrow[1].encode('ascii', 'ignore')
        self.uri = qrow[2]
        self.start_date = qrow[3]
        self.end_date = qrow[4]
        self.duration = qrow[5]
        self.mimetype = qrow[6]

    def playlistitem(self, default_date_string=None):
        return {
            "name" : self.name,
            "uri" : self.uri,
            "duration" : self.duration,
            "mimetype" : self.mimetype,
            "asset_id" : self.asset_id,
            "start_date" : datestring.date_to_string(self.start_date) if self.start_date else default_date_string,
            "end_date" : datestring.date_to_string(self.end_date) if self.end_date else default_date_string
            }
