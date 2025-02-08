import os
import requests
import csv
import time
import datetime

csv_filename = input('Output filename: ')
minimum_count = input('Minimum tag count (> 50 is preferable): ')
dashes = input('replace \'_\' with \'-\'? (often better for prompt following) (Y/n): ')
exclude = input('enter categories to exclude: (general,artist,copyright,character,post) (press enter for none): \n')
alias = input('Include aliases? (Only supported in tag-complete) (Y/n): ')
boards = input('Enter boards to scrape danbooru(d), e621(e), both(de) (default: danbooru): ')
date = input('Enter cutoff date. ex: 2024-09-03 for september 3rd 2024: ')
try:
    max_date =  datetime.datetime.strptime(date.strip()[:10], "%Y-%m-%d")
    print(f"Using date: {max_date}")
except:
    max_date = str(datetime.datetime.now())[:10]
    print(f"Using todays date: {max_date}")

boards = boards.lower()
if (not "d" in boards) and (not "e" in boards):
    boards = "d"

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

if not 'n' in alias.lower():
    alias = 'y'

if not minimum_count.isdigit():
    minimum_count = 50

# Base URLs
dan_base_url = 'https://danbooru.donmai.us/tags.json?limit=1000&search[hide_empty]=yes&search[is_deprecated]=no&search[order]=count'
dan_alias_url = 'https://danbooru.donmai.us/tag_aliases.json?commit=Search&search%5Bconsequent_name_matches%5D='
e6_base_url = 'https://e621.net/tags.json?limit=1000&search[hide_empty]=yes&search[is_deprecated]=no&search[order]=count'
e6_alias_url = 'https://e621.net/tag_aliases.json?commit=Search&search%5Bconsequent_name%5D='

session = requests.Session()

class Complete(Exception): pass

def get_aliases(tags, name, url, max_date, session):
    url = url + name
    while True:
        response = session.get(url,headers={"User-Agent": "tag-list/3.0"})
        if response.status_code == 200:
            aliases = {}
            data = response.json()
            for item in data:
                aliases[item['antecedent_name']] = item['antecedent_name'],item['created_at']

            aliases = {key: value for key, value in aliases.items() 
               if datetime.datetime.strptime(value[1][:10], "%Y-%m-%d") <= max_date}

            if datetime.datetime.strptime(tags[name][2][:10], "%Y-%m-%d") >= max_date:
                try:
                    previous_key = tags.pop(name)
                    tags[aliases[0][0]] = previous_key
                    lst_alias = []
                    for index in range(1, len(alias)):
                        lst_alias += alias[index][0]
                    tags[aliases[0][0]] += [lst_alias]
                    dan_tags[aliases[0][0]] += [''] # safety index
                    return
                except: # if there are no aliases for a tag which must be removed
                    print(f"Removed {name}")
                    return
            dan_tags[name] += [''] # safety index
        else:
            print("Failed to get aliases, likely a connection error.\nRetrying in 5 seconds...")  


if "d" in boards:
    dan_tags = {}
    try:
        for page in range(1, 1001):
            # Update the URL with the current page
            url = f'{dan_base_url}&page={page}'
            # Fetch the JSON data
            response = session.get(url,headers={"User-Agent": "tag-list/3.0"})
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
                        dan_tags[item['name']] = [item['category'],item['post_count'],item['created_at']]
                        get_aliases(dan_tags, item['name'], dan_alias_url, max_date, session)
            else:
                print(f'Failed to fetch data for page {page}. HTTP Status Code: {response.status_code}', flush=True)
                break
            print(f'Danbooru page {page} processed.', flush=True)
            # Sleep for 0.5 second because we have places to be
            time.sleep(0.5)
    except(Complete):
        pass

if "e" in boards:
    e6_tags = {}
    try:
        for page in range(1, 1001):
            # Update the URL with the current page
            url = f'{e6_base_url}&page={page}'
            # Fetch the JSON data
            response = session.get(url,headers={"User-Agent": "tag-list/3.0"})
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
                        get_aliases(e6_tags, item['name'], e6_alias_url, max_date, session)
            else:
                print(f'Failed to fetch data for page {page}. HTTP Status Code: {response.status_code}', flush=True)
                break
            print(f'e6 page {page} processed.', flush=True)
            # Sleep for 0.5 second because we have places to be
            time.sleep(0.5)
    except(Complete):
        pass

# Merge boards
if ("d" in boards) and ("e" in boards):
    for tag in dan_tags:
        if tag in e6_tags:
            e6_tags[tag][1] += dan_tags[tag][1] # combined count
    dan_tags.update(e6_tags)
    full_tags = dan_tags
elif "d" in boards:
    full_tags = dan_tags
else:
    full_tags = e6_tags

print("writing to file")
with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    # danbooru
    # Write the data
    for key, value in full_tags.items():
        if not str(value[0]) in excluded:
            if alias == 'n':
                writer.writerow([key,value[0],value[1],''])
            else:
                writer.writerow([key,value[0],value[1],value[3]])
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