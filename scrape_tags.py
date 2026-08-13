import os
import re
import html
import requests
import collections
import csv
import time
import datetime

class Complete(Exception): pass

csv_filename = input('Output filename: ')
minimum_count = input('Minimum tag count (> 50 is preferable): ')
dashes = input('replace \'_\' with \'-\'? (some sdxl based models work better this way) (Y/n): ')
ats = input('Add an \'@\' to artist names? (used by anima and some other models) (y/N): ')
exclude = input('enter categories to exclude: (general,artist,copyright,character,post) (press enter for none): \n')
boards = input('Enter boards to scrape danbooru(d), e621(e), gelbooru(g), or combinations like (deg) (default: danbooru): ')
date = input('Enter cutoff date (for aliases). ex: 2024-09-03 for september 3rd 2024: ')

try:
    max_date =  datetime.datetime.strptime(date.strip()[:10], "%Y-%m-%d")
    print(f"Using date: {max_date}")
except:
    max_date = datetime.datetime.now()
    print(f"Using todays date: {max_date}")

boards = boards.lower()
if (not "d" in boards) and (not "e" in boards) and (not "g" in boards):
    boards = "d"

# gelbooru requires an api key which requires an account, pray signups are active when you make one
if "g" in boards:
    print("Gelbooru selected. An API key + user id are required.")
    print("On gelbooru.com, open My Account -> Account Options and copy the full")
    print("'&api_key=...&user_id=...' string from the API Access section, then paste it below.")
    while True:
        raw = input('Paste your Gelbooru API credentials string: ').strip()
        # normalize to exactly one leading '&' regardless of what was copied
        gel_auth = '&' + raw.lstrip('&?').strip()
        if 'api_key=' in gel_auth and 'user_id=' in gel_auth:
            break
        print("That doesn't look right (expected something like '&api_key=...&user_id=...'). Please try again.")

excluded = ""
excluded += "0" if "general" in exclude else ""
excluded += "1" if "artist" in exclude else ""
excluded += "3" if "copyright" in exclude else ""
excluded += "4" if "character" in exclude else ""
excluded += "5" if "post" in exclude else ""

kaomojis = [
    "0_0", "(o)_(o)", "+_+", "+_-", "._.", "<o>_<o>", "<|>_<|>", "=_=", ">_<",
    "3_3", "6_9", ">_o", "@_@", "^_^", "o_o", "u_u", "x_x", "|_|", "||_||",
]

if not '.csv' in csv_filename:
    csv_filename += '.csv'

if not 'n' in dashes.lower():
    dashes = 'y'
    csv_filename += '-temp'

if not minimum_count.isdigit():
    minimum_count = 50

if not 'y' in ats.lower():
    ats = 'n'

# Base URLs without the page parameter
base_url = 'https://danbooru.donmai.us/tags.json?limit=1000&search[hide_empty]=yes&search[is_deprecated]=no&search[order]=count'
alias_url = 'https://danbooru.donmai.us/tag_aliases.json?commit=Search&limit=1000&search[order]=tag_count'
e6_base_url = 'https://e621.net/tags.json?limit=1000&search[hide_empty]=yes&search[is_deprecated]=no&search[order]=count'
e6_alias_url = 'https://e621.net/tag_aliases.json?commit=Search&limit=1000&search[order]=tag_count'
# gel must be gated because of extra parameter
if "g" in boards:
    gel_base_url = ('https://gelbooru.com/index.php?page=dapi&s=tag&q=index&json=1'
                    f'&limit=100&orderby=count{gel_auth}')

session = requests.Session()

dan_aliases = collections.defaultdict(str)
e6_aliases = collections.defaultdict(str)


def backdate(tags, aliases, date):
    print(f"Clearing older aliases")
    filtered_aliases = {}
    for key in aliases:
        kept = []
        for item in aliases[key]:
            entry_date = datetime.datetime.strptime(item[1][:10], "%Y-%m-%d")
            if entry_date <= date:
                kept += [item[0]]
        filtered_aliases[key] = kept

    #print(filtered_aliases)

    for key in list(tags.keys()): # prevents size change error
        #print(f"Processing {key}")
        if datetime.datetime.strptime(tags[key][2][:10], "%Y-%m-%d") > date:
            try:
                new_key = filtered_aliases[key].pop(0)
                value = tags.pop(key)
                tags[new_key] = value
            except Exception as e:
                #print(f"{key} removed\n{e}")
                pass

    # add aliases
    for key in filtered_aliases:
        try:
            alias_string = ",".join(filtered_aliases[key])
            tags[key] += [alias_string]
        except:
            #print(f"{key} probably doesn't exist in one list or the other, likely a cuttoff thing")
            pass


def get_aliases(url,type):
    # create alias dictionary
    try:
        aliases = collections.defaultdict(list)
        for page in range(1,1001):
            # Update the URL with the current page
            url = f'{url}&page={page}'
            # Fetch the JSON data
            while True:
                response = session.get(url,headers={"User-Agent": "tag-list/2.0"})
                if response.status_code == 200:
                    break
                else:
                    print(f"Couldn't reach server, Status: {response.status_code}.\nRetrying in 5 seconds")
                    time.sleep(5)
            data = response.json()
            # Break the loop if the data is empty (no more tags to fetch)
            if not data:
                print(f'No more data found at page {page}. Stopping.', flush=True)
                break
            for item in data:
                if type == "e": # danbooru doesn't have post counts for aliases
                    if int(item['post_count']) < int(minimum_count):
                        raise Complete
                aliases[item['consequent_name']] += [[item['antecedent_name'],item['created_at']]]
            print(f'Page {page} aliases processed.', flush=True)
            time.sleep(0.1) # avoid cloudflare rate limit
    except(Complete):
        print("reached the post threshold")
    return(aliases)


def get_gel_aliases():
    # gel doesn't provided aliases in the api so regular scraping is required
    print("Scraping Gelbooru aliases from the web listing (50/page, ~460 pages)...")
    aliases = collections.defaultdict(list)
    pid = 0
    while True:
        url = f'https://gelbooru.com/index.php?page=alias&s=list&pid={pid}'
        while True:
            response = session.get(url, headers={"User-Agent": "tag-list/2.0"})
            if response.status_code == 200:
                break
            print(f"Couldn't reach alias server, Status: {response.status_code}.\nRetrying in 5 seconds")
            time.sleep(5)
        # each alias is a <tr> containing the '&rarr;' arrow between two tag links:
        # antecedent (links[0]) -> consequent (links[1])
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', response.text, re.S)
        found = 0
        for row in rows:
            if 'rarr;' not in row:
                continue
            links = re.findall(r'page=post&amp;s=list&amp;tags=([^"&]+)', row)
            if len(links) >= 2:
                aliases[html.unescape(links[1])].append(html.unescape(links[0]))  # consequent -> [antecedents]
                found += 1
        if found == 0:
            print(f'No more aliases at pid {pid}. Stopping.', flush=True)
            break
        if pid % 500 == 0:  # log every 10 pages
            print(f'Gelbooru aliases: pid {pid} done ({sum(len(v) for v in aliases.values())} aliases so far).', flush=True)
        pid += 50
        time.sleep(1/3)  # ~3 req/s (gelbooru allows up to 10/s)
    return aliases

#######
if "d" in boards:
    dan_tags = {}
    try:
        for page in range(1,1001):
            # Update the URL with the current page
            url = f'{base_url}&page={page}'
            # Fetch the JSON data
            while True:
                response = session.get(url,headers={"User-Agent": "tag-list/2.0"})
                if response.status_code == 200:
                    break
                else:
                    print(f"Couldn't reach server, Status: {response.status_code}.\nRetrying in 5 seconds")
                    time.sleep(5)
            data = response.json()
            # Break the loop if the data is empty (no more tags to fetch)
            if not data:
                print(f'No more data found at page {page}. Stopping.', flush=True)
                break
            
            for item in data:
                if int(item['post_count']) < int(minimum_count): # break if below minimum count
                    raise Complete
                if not str(item['category']) in excluded:
                    dan_tags[item['name']] = [item['category'],item['post_count'],item['created_at']]
            print(f'Danbooru page {page} processed.', flush=True)
            time.sleep(0.1) # avoid cloudflare rate limit
    except(Complete):
        pass

if "d" in boards:
    dan_aliases = get_aliases(alias_url, "d")
    backdate(dan_tags,dan_aliases,max_date)


if "e" in boards:
    e6_tags = {}
    try:
        for page in range(1,1001):
            # Update the URL with the current page
            url = f'{e6_base_url}&page={page}'
            # Fetch the JSON data
            response = session.get(url,headers={"User-Agent": "tag-list/2.0"})
            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()
                # Break the loop if the data is empty (no more tags to fetch)
                if not data:
                    print(f'No more data found at page {page}. Stopping.', flush=True)
                    break
                
                for item in data:
                    if int(item['post_count']) < int(minimum_count): # break if below minimum count
                        raise Complete
                    if not str(item['category']) in excluded:
                        e6_tags[item['name']] = [item['category'],item['post_count'],item['created_at']]
            else:
                print(f'Failed to fetch data for page {page}. HTTP Status Code: {response.status_code}', flush=True)
                break
            print(f'e621 page {page} processed.', flush=True)
            # e6 gets mad if you make more than 1 per second
            time.sleep(1)
    except Complete:
        print(f'All tags with {minimum_count} posts or greater have been scraped.')

if "g" in boards:
    gel_tags = {}
    # always drop gelbooru's invalid (2) and deprecated (6) categories
    gel_excluded = excluded + '26'
    pid = 0
    try:
        while True:  # gelbooru doesn't cap pid; we stop on the count threshold or an empty page
            url = f'{gel_base_url}&pid={pid}'
            while True:
                response = session.get(url, headers={"User-Agent": "tag-list/2.0"})
                if response.status_code == 200:
                    break
                if response.status_code in (401, 403):
                    print(f"Gelbooru authentication failed (HTTP {response.status_code}). Check your API credentials. Skipping Gelbooru.")
                    break
                print(f"Couldn't reach server, Status: {response.status_code}.\nRetrying in 5 seconds")
                time.sleep(5)
            if response.status_code != 200:  # auth failed -> stop scraping gelbooru, keep what we have
                break
            try:
                data = response.json()
            except Exception:
                print(f"Could not parse JSON for pid {pid}. Stopping.", flush=True)
                break
            # gelbooru wraps results in a 'tag' key (a lone match comes back as a dict)
            if isinstance(data, dict):
                items = data.get('tag', [])
            else:
                items = data
            if isinstance(items, dict):
                items = [items]
            if not items:
                print(f'No more data found at pid {pid}. Stopping.', flush=True)
                break

            for item in items:
                if not item.get('name'):  # skip blank/garbage names (the all-time top entry is '')
                    continue
                if int(item['count']) < int(minimum_count):  # results are count-descending, so we're done
                    raise Complete
                if not str(item['type']) in gel_excluded:
                    # gelbooru has no created_at; store '' so the shape matches the other boards
                    gel_tags[item['name']] = [item['type'], int(item['count']), '']
            print(f'Gelbooru pid {pid} processed.', flush=True)
            pid += 1
            time.sleep(1/8)  # ~8 req/s (gelbooru allows up to 10/s)
    except Complete:
        print(f'All tags with {minimum_count} posts or greater have been scraped.')

if "g" in boards:
    # Attach gelbooru aliases
    gel_aliases = get_gel_aliases()
    for consequent, antecedents in gel_aliases.items():
        if consequent in gel_tags:
            gel_tags[consequent].append(','.join(antecedents))

# Merge boards
full_tags = {}
if "d" in boards:
    for tag, value in dan_tags.items():
        full_tags[tag] = list(value)
if "e" in boards:
    for tag, value in e6_tags.items():
        if tag in full_tags:
            full_tags[tag][1] += value[1]      # combined count
            full_tags[tag][0] = value[0]        # e6 wins category
            full_tags[tag][2] = value[2]        # e6 wins created_at
        else:
            full_tags[tag] = list(value)
if "g" in boards:
    for tag, value in gel_tags.items():
        if tag in full_tags:
            full_tags[tag][1] += value[1]
            full_tags[tag][0] = value[0]
            full_tags[tag][2] = value[2]
        else:
            full_tags[tag] = list(value)

# Open a file to write
print("writing to file")
with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    for key, value in full_tags.items():
        if not str(value[0]) in excluded:
            tag_name = key
            alias_string = ''
            try:
                alias_string = value[3]
            except:
                pass
            
            if ats == 'y' and str(value[0]) == '1':
                tag_name = '@' + key
                if alias_string:
                    aliases = alias_string.split(',')
                    aliases = ['@' + alias for alias in aliases]
                    alias_string = ','.join(aliases)
            
            writer.writerow([tag_name, value[0], value[1], alias_string])
    # Explicitly flush the data to the file
    file.close()

    if dashes == 'y':
        print(f'Replacing \'_\' with \'-\'')
        with open(csv_filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            with open(csv_filename.removesuffix('-temp'), 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.writer(outfile)
                for row in reader:
                    if not row[0] in kaomojis:
                        row[0] = row[0].replace("_", "-")
                        row[3] = row[3].replace("_", "-")
                    writer.writerow(row)
                outfile.close()    
            csvfile.close()
        os.remove(csv_filename)
        csv_filename = csv_filename.removesuffix('-temp')


print(f'Data has been written to {csv_filename}', flush=True)