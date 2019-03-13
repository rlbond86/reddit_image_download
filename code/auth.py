import praw

class Auth:
    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.user_agent = "reddit_image_download.py by /u/rlbond86"
        
    def readFromFile(self, filename):
        with open(filename, 'r') as f:
            lines = f.readlines()
            self.client_id = lines[0].strip()
            self.client_secret = lines[1].strip()
            
    def login(self):
        r = praw.Reddit(client_id=self.client_id, 
                        client_secret=self.client_secret, 
                        user_agent=self.user_agent)
        return r
    
