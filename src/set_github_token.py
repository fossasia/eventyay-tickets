import os

import toml

# Get the stripe_key from environment variable
github_token = os.getenv('GITHUB_TOKEN')

# Load the pyproject.toml file
pyproject = toml.load('/pretix/pyproject.toml')

# If github_token is None, remove the eventyay-stripe dependency

# Write the updated pyproject.toml back to file
with open('/pretix/pyproject.toml', 'w') as f:
    toml.dump(pyproject, f)
