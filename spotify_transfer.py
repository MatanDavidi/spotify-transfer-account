import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import sys

# --- CONFIGURATION ---
# IMPORTANT: Fill these in with your credentials from the Spotify Developer Dashboard
# It's recommended to use environment variables for security, but this works for a personal script.
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REDIRECT_URI = "YOUR REDIRECT URI"

# The permissions your script needs. This is a comprehensive list for the tasks.
SCOPE = "user-library-read user-library-modify playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-follow-read user-follow-modify"

# --- CACHE FILE PATHS ---
# These files will store the authentication tokens for each account
SOURCE_CACHE_PATH = ".cache-source"
DESTINATION_CACHE_PATH = ".cache-destination"

def get_all_paginated_items(spotify_client, initial_results):
    """Helper function to handle Spotify's pagination for any list of items."""
    items = initial_results['items']
    while initial_results['next']:
        initial_results = spotify_client.next(initial_results)
        items.extend(initial_results['items'])
    return items

def transfer_liked_songs(sp_source, sp_destination):
    """Transfers all liked songs from the source account to the destination account."""
    print("\n--- Starting Liked Songs Transfer ---")
    
    # 1. Get all liked songs from the source account
    print("Fetching liked songs from source account... (this might take a while)")
    results = sp_source.current_user_saved_tracks(limit=50)
    source_tracks = get_all_paginated_items(sp_source, results)
    
    source_track_ids = [item['track']['id'] for item in source_tracks if item.get('track')]
    print(f"Found {len(source_track_ids)} liked songs in source account.")

    # 2. Add songs to the destination account's library in batches of 50
    print("Adding songs to destination account's library...")
    for i in range(0, len(source_track_ids), 50):
        batch = source_track_ids[i:i+50]
        try:
            sp_destination.current_user_saved_tracks_add(tracks=batch)
            print(f"  Added batch {i//50 + 1}/{(len(source_track_ids) - 1)//50 + 1}")
        except Exception as e:
            print(f"  Could not add batch {i//50 + 1}. Error: {e}")
        time.sleep(1) # Be nice to the API

    print("--- Liked Songs Transfer Complete ---")


def transfer_followed_artists(sp_source, sp_destination):
    """Transfers all followed artists from the source account to the destination account."""
    print("\n--- Starting Followed Artists Transfer ---")
    
    # 1. Get all followed artists from the source account (cursor-based pagination)
    print("Fetching followed artists from source account...")
    source_artist_ids = []
    results = sp_source.current_user_followed_artists(limit=50)
    while True:
        source_artist_ids.extend([artist['id'] for artist in results['artists']['items']])
        if not results['artists']['next']:
            break
        results = sp_source.next(results['artists'])

    print(f"Found {len(source_artist_ids)} followed artists.")

    # 2. Follow artists on the destination account in batches of 50
    print("Following artists on destination account...")
    for i in range(0, len(source_artist_ids), 50):
        batch = source_artist_ids[i:i+50]
        try:
            sp_destination.user_follow_artists(ids=batch)
            print(f"  Followed batch {i//50 + 1}/{(len(source_artist_ids) - 1)//50 + 1}")
        except Exception as e:
            print(f"  Could not follow batch {i//50 + 1}. Error: {e}")
        time.sleep(1) # Be nice to the API

    print("--- Followed Artists Transfer Complete ---")


def transfer_playlists(sp_source, sp_destination, source_user_id):
    """Transfers playlists. Re-creates owned playlists and follows other playlists."""
    print("\n--- Starting Playlists Transfer ---")
    
    # Get all of destination's current playlists to avoid creating duplicates
    print("Fetching destination's existing playlists to avoid duplicates...")
    dest_playlists_results = sp_destination.current_user_playlists(limit=50)
    dest_playlists = get_all_paginated_items(sp_destination, dest_playlists_results)
    dest_playlist_names = {p['name'] for p in dest_playlists}
    print(f"Found {len(dest_playlist_names)} playlists on destination account.")

    # Get all of source's playlists
    print("Fetching source account's playlists...")
    source_playlists_results = sp_source.current_user_playlists(limit=50)
    source_playlists = get_all_paginated_items(sp_source, source_playlists_results)
    print(f"Found {len(source_playlists)} total playlists on source account to process.")

    for i, playlist in enumerate(source_playlists):
        print(f"\nProcessing playlist {i+1}/{len(source_playlists)}: '{playlist['name']}'")

        # Case 1: The playlist is owned by the source user. Re-create it.
        if playlist['owner']['id'] == source_user_id:
            print(f"  -> This is an owned playlist. Attempting to re-create.")
            
            if playlist['name'] in dest_playlist_names:
                print(f"  -> SKIPPING: A playlist named '{playlist['name']}' already exists on the destination account.")
                continue

            # Create a new empty playlist on the destination account
            try:
                new_playlist = sp_destination.user_playlist_create(
                    user=sp_destination.me()['id'],
                    name=playlist['name'],
                    public=playlist['public'],
                    collaborative=playlist['collaborative'],
                    description=playlist['description']
                )
                print(f"  -> Successfully created new empty playlist '{new_playlist['name']}'.")
            except Exception as e:
                print(f"  -> ERROR: Could not create playlist. {e}")
                continue
            
            # Get all tracks from the original playlist
            print("  -> Fetching tracks from original playlist...")
            original_tracks_results = sp_source.playlist_tracks(playlist['id'], limit=100)
            original_tracks = get_all_paginated_items(sp_source, original_tracks_results)
            track_uris = [item['track']['uri'] for item in original_tracks if item.get('track') and item['track'].get('uri')]
            
            # Add tracks to the new playlist in batches of 100
            if track_uris:
                print(f"  -> Adding {len(track_uris)} tracks to new playlist...")
                for j in range(0, len(track_uris), 100):
                    batch = track_uris[j:j+100]
                    try:
                        sp_destination.playlist_add_items(new_playlist['id'], batch)
                        print(f"    -> Added batch {j//100 + 1}/{(len(track_uris) - 1)//100 + 1}")
                    except Exception as e:
                        print(f"    -> ERROR: Could not add batch. {e}")
                    time.sleep(1) # Be nice to the API
            else:
                print("  -> Playlist is empty, no tracks to add.")

        # Case 2: The playlist is followed by the source user. Just follow it.
        else:
            print(f"  -> This is a followed playlist. Attempting to follow.")
            try:
                sp_destination.user_playlist_follow_playlist(playlist['id'])
                print(f"  -> Successfully followed '{playlist['name']}'.")
            except Exception as e:
                # This often fails if the user already follows the playlist, which is fine.
                print(f"  -> INFO: Could not follow playlist (maybe already followed?). Error: {e}")
        time.sleep(1)

    print("\n--- Playlists Transfer Complete ---")


def main():
    """Main function to orchestrate the entire transfer process."""
    # Check for credentials
    if CLIENT_ID == "YOUR_CLIENT_ID" or CLIENT_SECRET == "YOUR_CLIENT_SECRET":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERROR: Please fill in your CLIENT_ID and CLIENT_SECRET. !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1)

    # Check for cache files
    if not os.path.exists(SOURCE_CACHE_PATH) or not os.path.exists(DESTINATION_CACHE_PATH):
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERROR: Cache files not found.                         !!!")
        print("!!! Please run the `generate_token.py` script for both    !!!")
        print("!!! accounts and rename the cache files to                !!!")
        print("!!! '.cache-source' and '.cache-destination' respectively.!!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1)

    # Authenticate both clients
    print("Authenticating accounts...")
    try:
        sp_source = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
            scope=SCOPE, cache_path=SOURCE_CACHE_PATH
        ))
        sp_destination = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
            scope=SCOPE, cache_path=DESTINATION_CACHE_PATH
        ))
        
        source_user = sp_source.me()
        dest_user = sp_destination.me()
        print(f"Successfully authenticated!")
        print(f"  Source account:      {source_user['display_name']} ({source_user['id']})")
        print(f"  Destination account: {dest_user['display_name']} ({dest_user['id']})")

    except Exception as e:
        print(f"Error during authentication: {e}")
        print("Your cache files might be invalid. Try deleting them and re-generating.")
        sys.exit(1)

    # --- RUN THE TRANSFERS ---
    # You can comment out any of these lines if you only want to transfer specific things.
    transfer_liked_songs(sp_source, sp_destination)
    transfer_followed_artists(sp_source, sp_destination)
    transfer_playlists(sp_source, sp_destination, source_user['id'])

    print("\n\n##################################")
    print("###      TRANSFER FINISHED     ###")
    print("##################################")


if __name__ == "__main__":
    main()