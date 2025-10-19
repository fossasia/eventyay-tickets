# Twemoji SVG Files

This directory contains all Twemoji SVG files for local emoji rendering.

## Source
- **Version:** Twemoji v14.0.2
- **Repository:** https://github.com/twitter/twemoji
- **License:** CC-BY 4.0 and MIT (see https://github.com/twitter/twemoji/blob/master/LICENSE)

## Contents
- **Total Files:** 3,690 SVG files
- **Size:** ~22 MB
- **Format:** Individual SVG files named by Unicode codepoint (e.g., `1f600.svg` for 😀)

## Usage
These files are referenced by the application's emoji rendering system (`src/lib/emoji.js`) to display emojis without external CDN dependencies.

## Update Process
To update to a newer version of Twemoji:

```bash
cd /path/to/webapp/public/twemoji/svg
# Remove old files
rm *.svg
# Download new version (replace version number as needed)
curl -fsSL https://github.com/twitter/twemoji/archive/refs/tags/v14.0.2.tar.gz | tar -xz --strip-components=3 twemoji-14.0.2/assets/svg
```

## Key Emojis for Chat Reactions
The following 5 emojis are used as quick reactions in the chat system:
- 👏 (1f44f.svg) - Clapping hands
- ❤️ (2764.svg) - Red heart
- 👍 (1f44d.svg) - Thumbs up
- 🤣 (1f923.svg) - Rolling on floor laughing
- 😮 (1f62e.svg) - Face with open mouth
