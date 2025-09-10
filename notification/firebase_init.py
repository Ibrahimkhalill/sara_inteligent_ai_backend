# notification/firebase_init.py
import os
import firebase_admin
from firebase_admin import credentials

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cred_path = os.path.join(BASE_DIR, "notification", "ailearningauthentication-firebase-adminsdk-fbsvc-21f1cf7705.json")

# Initialize Firebase app only if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
