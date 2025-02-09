import os
import requests
import collections
import csv
import time
import datetime

class Complete(Exception): pass

csv_filename = input('Output filename: ')
minimum_count = input('Minimum tag count (> 50 is preferable): ')
dashes = input('replace \'_\' with \'-\'? (often better for prompt following) (Y/n): ')
exclude = input('enter categories to exclude: (general,artist,copyright,character,post) (press enter for none): \n')
boards = input('Enter boards to scrape danbooru(d), e621(e), both(de) (default: danbooru): ')
date = input('Enter cutoff date. ex: 2024-09-03 for september 3rd 2024: ')
try:
    max_date =  datetime.datetime.strptime(date.strip()[:10], "%Y-%m-%d")
    print(f"Using date: {max_date}")
except:
    max_date = datetime.datetime.now()
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

if not minimum_count.isdigit():
    minimum_count = 50

# Base URLs without the page parameter
base_url = 'https://danbooru.donmai.us/tags.json?limit=1000&search[hide_empty]=yes&search[is_deprecated]=no&search[order]=count'
alias_url = 'https://danbooru.donmai.us/tag_aliases.json?commit=Search&limit=1000&search[order]=tag_count'
e6_base_url = 'https://e621.net/tags.json?limit=1000&search[hide_empty]=yes&search[is_deprecated]=no&search[order]=count'
e6_alias_url = 'https://e621.net/tag_aliases.json?commit=Search&limit=1000&search[order]=tag_count'

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
        for page in range(1,5):
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

#######
if "d" in boards:
    dan_tags = {}
    try:
        for page in range(1, 5):
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
        for page in range(1, 2):
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

# e6 tags are fucked, a proper solution would take ~10 hours per list and I'm not going that far for furries
#if "e" in boards:
#    e6_aliases = get_aliases(e6_alias_url, "e")
#    backdate(e6_tags,e6_aliases,max_date)


# Merge boards
if ("d" in boards) and ("e" in boards):
    for tag in dan_tags:
        if tag in e6_tags:
            e6_tags[tag][1] += dan_tags[tag][1] # combined count
            """if e6_tags[tag][2] != None and dan_tags[tag][2] != None:
                if e6_tags[tag][2] == "":
                    e6_tags[tag][2] += dan_tags[tag][2]  # aliases
                else:
                    e6_tags[tag][2] += "," + dan_tags[tag][2]"""
    dan_tags.update(e6_tags)
    full_tags = dan_tags
elif "d" in boards:
    full_tags = dan_tags
else:
    full_tags = e6_tags

# Open a file to write
print("writing to file")
with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    # danbooru
    # Write the data
    for key, value in full_tags.items():
        if not str(value[0]) in excluded:
            try:
                writer.writerow([key,value[0],value[1],value[3]])
            except:
                writer.writerow([key,value[0],value[1],'']) #too lazy for a proper fix
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