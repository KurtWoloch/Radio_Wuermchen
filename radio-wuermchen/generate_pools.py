"""
Generate show-specific suggestion pools from the main playlist.
Each pool is defined by a set of filter rules (artist names, keywords, etc.).
"""
import os
import re
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")

def load_playlist():
    with open(PLAYLIST_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def basename(path):
    return os.path.splitext(os.path.basename(path))[0]

def filter_by_artists(playlist, artists):
    """Filter tracks where the filename starts with one of the given artist names."""
    results = []
    for track in playlist:
        name = basename(track).lower()
        for artist in artists:
            if name.startswith(artist.lower()):
                results.append(basename(track))
                break
    return sorted(set(results))

def filter_by_keywords(playlist, keywords, exclude_keywords=None):
    """Filter tracks where the filename contains any of the keywords."""
    exclude_keywords = exclude_keywords or []
    results = []
    for track in playlist:
        name = basename(track).lower()
        if any(kw.lower() in name for kw in keywords):
            if not any(ex.lower() in name for ex in exclude_keywords):
                results.append(basename(track))
    return sorted(set(results))

def write_pool(filename, header, tracks):
    path = os.path.join(SCRIPT_DIR, filename)
    tracks = list(tracks)
    random.shuffle(tracks)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"# {header}\n")
        for t in tracks:
            f.write(t + "\n")
    print(f"  {filename}: {len(tracks)} tracks")

def main():
    playlist = load_playlist()
    print(f"Loaded {len(playlist)} tracks from playlist.\n")

    # --- Rat Pack / Classic Crooners ---
    ratpack_artists = [
        "Frank Sinatra", "Dean Martin", "Sammy Davis Jr",
        "Nat King Cole", "Tony Bennett", "Louis Armstrong",
        "Ella Fitzgerald", "Perry Como", "Bobby Darin", "Louis Prima",
        "Bing Crosby", "Andy Williams", "Mel Torme", "Robbie Williams",
        "Dinah Washington", "Sarah Vaughan", "Peggy Lee",
    ]
    write_pool("suggestion_pool_ratpack.txt", "Suggestion Pool: Classic Crooners / Rat Pack",
               filter_by_artists(playlist, ratpack_artists))

    # --- Espresso (Disco / Electropop / Synth Pop / Fast) ---
    espresso_artists = [
        "Abba", "Boney M", "Bee Gees", "Donna Summer", "Gloria Gaynor",
        "KC and the Sunshine Band", "KC & the Sunshine Band",
        "Pet Shop Boys", "Depeche Mode", "New Order",
        "Erasure", "Kraftwerk", "OMD", "Yazoo", "Soft Cell",
        "Eurythmics", "A-ha", "Alphaville", "Modern Talking",
        "Bronski Beat", "Communards", "Human League",
        "Frankie Goes to Hollywood", "Dead or Alive",
        "Nena", "Falco", "La Bouche", "Snap", "Technotronic",
        "C+C Music Factory", "Crystal Waters", "Haddaway",
        "Corona", "2 Unlimited", "Ace of Base",
        "Daft Punk", "Gorillaz", "MGMT", "Peter Kent",
    ]
    espresso_keywords = ["disco", "dance mix", "remix", "club mix", "synth"]
    tracks_espresso = filter_by_artists(playlist, espresso_artists)
    tracks_espresso += filter_by_keywords(playlist, espresso_keywords)
    write_pool("suggestion_pool_espresso.txt", "Suggestion Pool: Espresso (Disco / Electropop / Synth Pop)",
               sorted(set(tracks_espresso)))

    # --- Indie / Alternative / The Music Box ---
    indie_artists = [
        "Radiohead", "Portishead", "Massive Attack", "Morcheeba",
        "Coldplay", "Arctic Monkeys", "The Killers", "Franz Ferdinand",
        "Bloc Party", "Interpol", "The Strokes", "White Stripes",
        "Arcade Fire", "Florence", "Vampire Weekend", "Tame Impala",
        "Pixies", "Sonic Youth", "The Cure", "Siouxsie",
        "Joy Division", "Bauhaus", "Echo & the Bunnymen",
        "Cocteau Twins", "The Smiths", "Morrissey",
        "R.E.M.", "Talking Heads", "The National",
        "Mogwai", "Sigur Ros", "Bjork", "Air", "Zero 7",
        "Hooverphonic", "Lamb", "Sneaker Pimps", "Tricky",
        "Garbage", "Placebo", "Muse", "Weezer",
    ]
    indie_keywords = ["indie", "alternative", "downtempo"]
    tracks_indie = filter_by_artists(playlist, indie_artists)
    tracks_indie += filter_by_keywords(playlist, indie_keywords)
    write_pool("suggestion_pool_indie.txt", "Suggestion Pool: The Music Box (Alternative / Indie)",
               sorted(set(tracks_indie)))

    # --- Evergreens (pre-1970) ---
    evergreen_artists = [
        "Elvis", "Beatles", "Rolling Stones", "Beach Boys",
        "Chuck Berry", "Buddy Holly", "Little Richard", "Fats Domino",
        "Ray Charles", "Aretha Franklin", "Otis Redding", "Sam Cooke",
        "The Supremes", "The Temptations", "Four Tops", "Marvin Gaye",
        "Stevie Wonder",  # early career
        "Simon & Garfunkel", "Bob Dylan", "Joan Baez",
        "The Mamas & the Papas", "The Byrds", "The Doors",
        "Jimi Hendrix", "Janis Joplin", "The Who",
        "Cream", "The Kinks", "The Animals", "The Yardbirds",
        "Dusty Springfield", "Petula Clark", "Tom Jones",
        "Frank Sinatra", "Dean Martin", "Nat King Cole",
        "Louis Armstrong", "Ella Fitzgerald",
        "Shirley Bassey", "Connie Francis", "Brenda Lee",
        "The Platters", "The Drifters", "The Shirelles",
        "Roy Orbison", "Johnny Cash", "Patsy Cline",
        "Bill Haley", "The Everly Brothers",
    ]
    write_pool("suggestion_pool_evergreens.txt", "Suggestion Pool: Evergreens (pre-1970s classics)",
               filter_by_artists(playlist, evergreen_artists))

    # --- Super Hits (70s and 80s) ---
    superhits_artists = [
        "Queen", "Abba", "Bee Gees", "Fleetwood Mac", "Eagles",
        "Michael Jackson", "Madonna", "Prince", "Whitney Houston",
        "Phil Collins", "Genesis", "Peter Gabriel", "Bonnie Tyler",
        "David Bowie", "Elton John", "Billy Joel", "Bruce Springsteen",
        "Tina Turner", "Cyndi Lauper", "Pat Benatar",
        "Blondie", "Duran Duran", "Spandau Ballet", "Culture Club",
        "Wham", "George Michael", "Rick Astley", "Europe",
        "The Police", "Sting", "U2", "Dire Straits",
        "AC/DC", "AC_DC", "Bon Jovi", "Def Leppard", "Van Halen",
        "Journey", "Foreigner", "Toto", "Survivor", "REO Speedwagon",
        "Hall & Oates", "Huey Lewis", "Simple Minds",
        "Tears for Fears", "The Bangles", "Bananarama",
        "Electric Light Orchestra", "ELO", "Supertramp",
        "Bee Gees", "Donna Summer", "Gloria Gaynor",
        "Earth Wind & Fire", "Earth, Wind & Fire", "Kool & the Gang",
        "Chic", "Sister Sledge", "Village People",
        "Rainhard Fendrich", "Wolfgang Ambros", "Georg Danzer",
        "Falco", "Opus", "STS",
    ]
    write_pool("suggestion_pool_superhits.txt", "Suggestion Pool: Super Hits (70s & 80s)",
               filter_by_artists(playlist, superhits_artists))

    # --- Friendly / Positive ---
    friendly_keywords = [
        "happy", "sunshine", "wonderful", "celebration", "joy",
        "smile", "beautiful", "good", "love", "dancing",
        "together", "friend", "party", "fun", "alive",
        "walking on", "feeling good", "best day", "bright",
    ]
    friendly_exclude = ["kill", "die", "dead", "war", "blood", "hate", "cry", "sad", "pain", "nightmare"]
    write_pool("suggestion_pool_friendly.txt", "Suggestion Pool: Please Be Friendly (positive vibes)",
               filter_by_keywords(playlist, friendly_keywords, friendly_exclude))

    # --- Modern (2010s / 2020s) ---
    modern_artists = [
        "Ed Sheeran", "Adele", "Taylor Swift", "Billie Eilish",
        "Dua Lipa", "Harry Styles", "Olivia Rodrigo", "The Weeknd",
        "Post Malone", "Drake", "Ariana Grande", "Bruno Mars",
        "Sia", "Lorde", "Sam Smith", "Hozier",
        "Imagine Dragons", "Twenty One Pilots", "Bastille",
        "Lana Del Rey", "Halsey", "Khalid", "Lizzo",
        "Doja Cat", "Bad Bunny", "BTS", "Blackpink",
        "Glass Animals", "Tones and I", "Lewis Capaldi",
        "Rag'n'Bone Man", "Tom Walker", "George Ezra",
        "Ava Max", "Miley Cyrus", "Lady Gaga",
        "Cardi B", "Megan Thee Stallion", "SZA",
    ]
    modern_keywords = ["2010", "2011", "2012", "2013", "2014", "2015",
                       "2016", "2017", "2018", "2019", "2020", "2021",
                       "2022", "2023", "2024", "2025", "2026"]
    tracks_modern = filter_by_artists(playlist, modern_artists)
    tracks_modern += filter_by_keywords(playlist, modern_keywords)
    write_pool("suggestion_pool_modern.txt", "Suggestion Pool: Music for Young People (2010s-2020s)",
               sorted(set(tracks_modern)))

    # --- Dreaming (soft/slow/easy listening) ---
    dreaming_artists = [
        "Enya", "Norah Jones", "Sade", "Chris Rea", "John Denver",
        "Lionel Richie", "Barry White", "Luther Vandross",
        "Air", "Zero 7", "Massive Attack", "Portishead",
        "Enigma", "Mike Oldfield", "Vangelis", "Jean-Michel Jarre",
        "Chet Baker", "Miles Davis", "John Coltrane", "Kenny Rogers",
        "Diana Krall", "Katie Melua", "Eva Cassidy", "Barbra Streisand",
    ]
    dreaming_keywords = [
        "dream", "lullaby", "sleep", "night", "moon", "star",
        "gentle", "soft", "quiet", "peace", "ballad",
        "love story", "unchained melody", "close to you",
        "blue eyes", "bright eyes", "angel", "heaven",
        "music of the night", "theme from",
    ]
    dreaming_exclude = ["nightmare", "shook me all night", "murder", "fight", "party all night", "late night"]
    tracks_dreaming = filter_by_artists(playlist, dreaming_artists)
    tracks_dreaming += filter_by_keywords(playlist, dreaming_keywords, dreaming_exclude)
    write_pool("suggestion_pool_dreaming.txt", "Suggestion Pool: Music for Dreaming",
               sorted(set(tracks_dreaming)))

    print("\nDone! All pools generated.")

if __name__ == "__main__":
    main()
