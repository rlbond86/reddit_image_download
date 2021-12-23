import sqlite3
import os.path

class Database:
    _this_version = 1
    _ext = '.db'

    def __init__(self, filename):
        if os.path.splitext(filename)[1] != self._ext:
            raise Exception(f'Database must end in .db but name is configured as {filename}')
        self._filename = filename
        self._con = sqlite3.connect(filename)
        self._con.row_factory = sqlite3.Row
        self._update_to_next_rev = [self._update_from_ver0]
        self._prepare_database()

    
    def _prepare_database(self):
        version = 0
    
        with self._con:
            version = self._con.execute("PRAGMA user_version").fetchone()[0]
    
        if version > self._this_version:
            raise Exception(f'Database version {version} is newer than script version {_this_version}')
    
        for ver in range(version, self._this_version):
            self._update_to_next_rev[ver]()
    
        self._clean_database()
    
    
    def delete_very_old_entries(self, num_days):
        with self._con:
            c = self._con.execute("""DELETE FROM images
                                     WHERE created < datetime('now', '-' || ? || ' days')""",
                                     (num_days,))
            return c.rowcount
    
    
    def exclude_old_entries(self, num_days):
        with self._con:
            c = self._con.execute("""UPDATE images
                                     SET excluded = 1
                                     WHERE created < datetime('now', '-' || ? || ' days')""",
                                     (num_days,))
            return c.rowcount
    
    
    def exclude_url(self, url):
        with self._con:
            self._con.execute("""UPDATE images
                                 SET excluded = 1
                                 where url = ?""",
                                 (url,))
    
    
    def set_filename(self, url, filename):
        with self._con:
            self._con.execute("""UPDATE images
                                 SET filename = ?
                                 WHERE url = ?""",
                                 (filename, url))
                                 
                                 
    def get_next_to_download(self):
        with self._con:
            c = self._con.execute("""SELECT * FROM images
                                     WHERE excluded = 0 AND filename IS NULL
                                     ORDER BY rowid
                                     LIMIT 1""")
            return c.fetchone()
            
            
    def get_image_count(self):
        with self._con:
            c = self._con.execute("""SELECT count(*) FROM images
                                     WHERE excluded = 0 AND filename IS NOT NULL""")
            return c.fetchone()[0]
    
    
    def exclude_missing_urls(self, urllist):
        with self._con:
            self._con.execute("""DROP TABLE IF EXISTS temp.urls""")
            self._con.execute("""CREATE TABLE temp.urls(url TEXT PRIMARY KEY)""")
            self._con.executemany("""INSERT OR IGNORE INTO temp.urls
                                     VALUES(?)""",
                                  ((url,) for url in urllist))
            c = self._con.execute("""DELETE FROM images
                                     WHERE url NOT IN
                                        (SELECT url FROM temp.urls)""")
            n = c.rowcount
            self._con.execute("""DROP TABLE IF EXISTS temp.urls""")
            
            return n
    
    
    def get_untracked_files(self, filelist):
        with self._con:
            self._con.execute("""DROP TABLE IF EXISTS temp.filenames""")
            self._con.execute("""CREATE TABLE temp.filenames(filename TEXT PRIMARY KEY)""")
            self._con.executemany("""INSERT INTO temp.filenames
                                     VALUES(?)""",
                                  ((filename,) for filename in filelist))
            c = self._con.execute("""SELECT temp.filenames.filename
                                     FROM temp.filenames
                                     LEFT JOIN images ON temp.filenames.filename = images.filename
                                     WHERE images.filename IS NULL OR images.excluded = 1""")
            return [item[0] for item in c.fetchall() if not os.path.splitext(item[0])[1].startswith(self._ext)]
    
    
    def register_image(self, url, title, user, subreddit, postid):
        with self._con:
           self._con.execute("""INSERT OR IGNORE INTO images(title, user, subreddit, url, postid)
                                VALUES(?,?,?,?,?)""", (title,user,subreddit,url,postid))
    
    
    def track_image(self, url, filename):
        with self._con:
            self._con.execute("""UPDATE images
                                 SET filename = ?
                                 WHERE url = ?""", (filename, url))
    
    
    def _update_from_ver0(self):
        # Nothing needs to be done for this case
        pass
    
    
    def _clean_database(self):
        with self._con:
            self._con.execute("""CREATE TABLE IF NOT EXISTS images(
                                 rowid     INTEGER  PRIMARY KEY   AUTOINCREMENT,
                                 filename  TEXT     UNIQUE,
                                 title     TEXT     NOT NULL,
                                 user      TEXT     NOT NULL,
                                 subreddit TEXT     NOT NULL,
                                 url       TEXT     UNIQUE   NOT NULL,
                                 postid    TEXT     UNIQUE   NOT NULL,
                                 created   DATETIME DEFAULT(CURRENT_TIMESTAMP),
                                 excluded  INTEGER  DEFAULT(0))""")
    
            self._con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS images_filename_idx
                                 ON images(filename)""")
            self._con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS images_url_idx
                                 ON images(url)""")
    
            self._con.execute("VACUUM")
            self._con.execute("PRAGMA user_version=1")


