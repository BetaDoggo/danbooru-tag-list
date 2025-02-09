I was looking for an updated danbooru tag list but I couldn't find a recent one that was in the correct format, so I made my own.

Based on this original script: https://gist.github.com/bem13/596ec5f341aaaefbabcbf1468d7852d5

requires the requests library (`pip install requests`)

[**Go To Model Tags**](https://github.com/BetaDoggo/danbooru-tag-list/releases/tag/Model-Tags)

Main Changes:
- Allows setting minimum post threshold
- Allows '-' format (found to be better for prompt following)
- Saves tag categories (used by SwarmUI and tag-complete)
- Uses the UI's expected formatting
- Slightly faster rate limit
- Ability to exclude tag categories
- aliases (UI support varies) (danbooru aliases only)
- supports pulling tags from e621 (optional)
- supports setting a cutoff date (applies to danbooru only)

About the uploaded lists:

I've uploaded premade versions of every all-category list with the minimum threshold set to 50, and aliases enabled. Aliases are only currently supported for danbooru because e621 has way too many and some overlap with real danbooru tags. There's some half working commented out code that will also pull aliases from e621 which I might support for e621-only lists, but for now I don't want to look at any more furry art.

The format is as follows:

|tag|category|post count|aliases(if enabled)|
|---|--------|----------|-----------------------------------------|
