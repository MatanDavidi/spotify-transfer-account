import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sys

# --- CONFIGURATION (Must match the main script) ---
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REDIRECT_URI = "YOUR REDIRECT URI"
SCOPE = "user-library-read user-library-modify playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-follow-read user-follow-modify"

def generate_token():
    """
    This script guides you through the Spotify authentication process.
    It will open a browser window for you to log in and authorize the app.
    After successful login, a '.cache' file will be created.
    
    You need to run this script TWICE:
    1. For the SOURCE account. After it runs, rename '.cache' to '.cache-source'.
    2. For the DESTINATION account. After it runs, rename '.cache' to '.cache-destination'.
    """
    if CLIENT_ID == "YOUR_CLIENT_ID" or CLIENT_SECRET == "YOUR_CLIENT_SECRET":
        print("ERROR: Please fill in your CLIENT_ID and CLIENT_SECRET before running.")
        sys.exit(1)

    print("--- Spotify Token Generation ---")
    print("A browser window will now open. Please log in with the desired Spotify account.")
    print("If you are running this for the first time, log in with your SOURCE account.")
    print("If you have already created '.cache-source', log in with your DESTINATION account.")
    
    try:
        auth_manager = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            # We don't specify a cache_path here so it defaults to '.cache'
        )
        # This line triggers the authentication flow
        sp = spotipy.Spotify(auth_manager=auth_manager)
        user = sp.me()
        
        print("\nSuccessfully authenticated as:", user['display_name'])
        print("A file named '.cache' has been created in this directory.")
        print("\nIMPORTANT: RENAME this file to '.cache-source' or '.cache-destination' based on which account you just used.")
        
    except Exception as e:
        print("\nAn error occurred during authentication:", e)

if __name__ == "__main__":
    generate_token()