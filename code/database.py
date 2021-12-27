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
            where_query = """"""
            c = self._con.execute("""   SELECT 
                                            postcode, title
                                        FROM 
                                            posts
                                        WHERE
                                            lastseen < datetime('now', '-' || ? || ' days')""",
                                  (num_days,))
            result = c.fetchall()
            self._con.execute("""   DELETE FROM
                                        posts
                                    WHERE
                                        lastseen < datetime('now', '-' || ? || ' days')""",
                              (num_days,))
            return result
            
            
    def _get_exclusion_sequence(self):
        with self._con:
            c = self._con.execute("""   SELECT 
                                            max(sequence) 
                                        FROM 
                                            excluded""")
            result = c.fetchone()[0]
            return result if result is not None else 0
            
            
    def exclude_old_entries(self, num_days):
        with self._con:
            seq = self._get_exclusion_sequence() + 1
            self._con.execute("""   INSERT OR IGNORE INTO 
                                        excluded
                                    SELECT 
                                        posts.id, ?, 'old'
                                    FROM
                                        posts
                                        JOIN localfiles
                                            ON posts.id = localfiles.postid
                                    WHERE
                                        localfiles.timestamp < datetime('now', '-' || ? || ' days')""",
                              (seq, num_days))
            self._con.execute("""   DELETE FROM
                                        localfiles
                                    WHERE 
                                        postid IN
                                            (   SELECT 
                                                    postid 
                                                FROM
                                                    excluded)""")
            c = self._con.execute("""   SELECT
                                            postcode, title
                                        FROM 
                                            posts
                                            JOIN excluded
                                                ON posts.id = excluded.postid
                                        WHERE excluded.sequence = ?""",
                                  (seq,))
            return c.fetchall()
            
            
    def exclude_unpopular_urls(self, urllist):
        with self._con:
            seq = self._get_exclusion_sequence() + 1
            self._con.execute("""   DROP TABLE IF EXISTS
                                        temp.urls_to_remove""")
            self._con.execute("""   CREATE TABLE
                                        temp.urls_to_remove
                                    AS
                                        SELECT
                                            url, id, postcode, title
                                        FROM
                                            posts
                                        WHERE
                                            id NOT IN
                                                (   SELECT 
                                                        postid
                                                    FROM
                                                        excluded)""")
            self._con.executemany("""   DELETE FROM
                                            temp.urls_to_remove
                                        WHERE
                                            url = ?""",
                                  ((url,) for url in urllist))
            self._con.execute("""   INSERT OR IGNORE INTO
                                        excluded
                                    SELECT
                                        id, ?, 'unpopular'
                                    FROM
                                        temp.urls_to_remove""",
                              (seq,))
            self._con.execute("""   DELETE FROM
                                        localfiles
                                    WHERE
                                        postid in
                                            (   SELECT
                                                    postid
                                                FROM
                                                    excluded)""")
            c = self._con.execute("""   SELECT
                                            url, postcode, title
                                        FROM
                                            temp.urls_to_remove""")
            result = c.fetchall()
            self._con.execute("""DROP TABLE temp.urls_to_remove""")
            
            return result
    
    
    def exclude_url(self, url, reason):
        with self._con:
            seq = self._get_exclusion_sequence() + 1
            self._con.execute("""   INSERT OR REPLACE INTO
                                        excluded
                                    SELECT
                                        id, ?, ?
                                    FROM
                                        posts
                                    WHERE
                                        url = ?""",
                              (seq, reason, url))
    
    
    def set_filename(self, url, filename):
        with self._con:
            self._con.execute("""   INSERT OR REPLACE INTO
                                        localfiles(postid, filename)
                                    SELECT
                                        id, ?
                                    FROM
                                        posts
                                    WHERE
                                        url = ?""",
                              (filename, url))
                                 
                                 
    def get_next_to_download(self):
        with self._con:
            c = self._con.execute("""   WITH
                                            tracked_posts
                                        AS
                                            (       SELECT
                                                        postid AS id
                                                    FROM
                                                        localfiles
                                                UNION
                                                    SELECT
                                                        postid AS id
                                                    FROM
                                                        excluded )
                                        SELECT
                                            posts.*
                                        FROM
                                            posts
                                        WHERE
                                            posts.id NOT IN tracked_posts
                                        ORDER BY
                                            posts.id
                                        LIMIT 1""")
            return c.fetchone()
            
            
    def get_image_count(self):
        with self._con:
            c = self._con.execute("""   SELECT
                                            count(*)
                                        FROM
                                            localfiles""")
            return c.fetchone()[0]
    
    
    def get_untracked_files(self, filelist):
        with self._con:
            self._con.execute("""   DROP TABLE IF EXISTS
                                        temp.files_in_directory""")
            self._con.execute("""   CREATE TABLE
                                        temp.files_in_directory(
                                            filename TEXT PRIMARY KEY)""")
            self._con.executemany("""   INSERT INTO
                                            temp.files_in_directory
                                        VALUES(?)""",
                                  ((filename,) for filename in filelist))
            c = self._con.execute("""   WITH
                                            valid_files
                                        AS
                                            (   SELECT
                                                    filename
                                                FROM
                                                    localfiles
                                                WHERE
                                                    postid NOT IN
                                                        (   SELECT
                                                                postid
                                                            FROM
                                                                excluded))
                                        SELECT
                                            filename
                                        FROM
                                            valid_files
                                        WHERE
                                            filename IN temp.files_in_directory""")
            result = [item[0] for item in c.fetchall() if not os.path.splitext(item[0])[1].startswith(self._ext)]
            self._con.execute("""DROP TABLE temp.files_in_directory""")
            return result
    
    
    def register_post(self, url, title, user, subreddit, postcode):
        with self._con:
           self._con.execute("""INSERT OR IGNORE INTO
                                    posts(title, user, subreddit, url, postcode, lastseen)
                                VALUES(?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                             (title, user, subreddit, url, postcode))
           self._con.execute("""UPDATE
                                    posts
                                SET
                                    lastseen = CURRENT_TIMESTAMP
                                WHERE
                                    url = ?""",
                             (url,))
    
    
    def track_image(self, url, filename):
        with self._con:
            self._con.execute("""   INSERT OR IGNORE INTO
                                        localfiles
                                    SELECT
                                        id, ?, CURRENT_TIMESTAMP
                                    FROM
                                        posts
                                    WHERE
                                        url = ?""",
                              (filename, url))
    
    
    def _update_from_ver0(self):
        # Nothing needs to be done for this case
        try:
            os.remove(".reddit_image_data")
        except:
            pass
    
    
    def _clean_database(self):
        with self._con:
            self._con.execute("""CREATE TABLE IF NOT EXISTS posts(
                                 id         INTEGER  PRIMARY KEY   AUTOINCREMENT,
                                 title      TEXT     NOT NULL,
                                 user       TEXT     NOT NULL,
                                 subreddit  TEXT     NOT NULL,
                                 url        TEXT     UNIQUE   NOT NULL,
                                 postcode   TEXT     UNIQUE   NOT NULL,
                                 lastseen   DATETIME NOT NULL)""")
            self._con.execute("""CREATE TABLE IF NOT EXISTS excluded(
                                 postid     INTEGER  REFERENCES posts(id)   NOT NULL,
                                 sequence   INTEGER,
                                 reason     TEXT)""")
            self._con.execute("""CREATE TABLE IF NOT EXISTS localfiles(
                                 postid     INTEGER  REFERENCES posts(id)   NOT NULL,
                                 filename   TEXT     UNIQUE   NOT NULL,
                                 timestamp  DATETIME NOT NULL)""")
            self._con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS excluded_postid_index
                                 ON excluded(postid)""")
            self._con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS localfiles_postid_index
                                 ON localfiles(postid)""")
            self._con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS localfiles_filename_index
                                 ON localfiles(filename)""")
            
            self._con.execute("VACUUM")
            self._con.execute("PRAGMA user_version = 1")
            self._con.execute("PRAGMA foreign_keys = ON")


