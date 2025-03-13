import json
import os

class Database:
    def __init__(self):
        self.database_path = "user_database.json"
        self.hist_path = self.init_hist("user_hist")
        self.user_base = self.get_user_database()

    def init_hist(self, hist_path):
        os.makedirs(hist_path, exist_ok=True)
        return hist_path

    def get_user_database(self):
        if os.path.exists(self.database_path):
            with open(self.database_path, "r+") as f:
                user_base = json.load(f)
        else:
            user_base = {}
        return user_base
    
    def write_to_database(self):
        with open(self.database_path, "w+") as f:
            json.dump(self.user_base, f)

    def get_user(self, user_id):
        return self.user_base.get(user_id, None)

    def insert_user(self, update):
        message = update.message
        user_id = message.from_user.id
        self.user_base[user_id] = {
            "user_id": user_id,
            "name":  message.from_user.first_name,
            "last_name":  message.from_user.last_name,
            "user_name":  message.from_user.username,
            "join_date": message.date.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.write_to_database()
        return self.get_user(user_id)

    def get_user_hist_path(self, user_id):
        return os.path.join(self.hist_path, f"{user_id}_hist.json")
    
    def get_user_history(self, user_id):
        if os.path.exists(self.get_user_hist_path(user_id)):
            with open(self.get_user_hist_path(user_id), "r+") as f:
                return json.load(f)
        else:
            return []

    def upsert_user_history(self, user_id, message): 
        cur_hist = self.get_user_history(user_id)
        cur_hist.append({
            "role": message["role"],
            "content": message["content"]
        })
        with open(self.get_user_hist_path(user_id), "w+") as f:
            json.dump(cur_hist, f)