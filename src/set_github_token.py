import os
import toml

# Get the stripe_key from environment variable
github_token = os.getenv('GITHUB_TOKEN')

# Load the pyproject.toml file
pyproject = toml.load('/pretix/pyproject.toml')

# Iterate over the dependencies
for i, dep in enumerate(pyproject['project']['dependencies']):
    if dep.startswith('eventyay-stripe'):
        # Update the stripe dependency with the stripe_key
        pyproject['project']['dependencies'][i] = f'eventyay-stripe @ git+https://{github_token}@github.com/fossasia/eventyay-tickets-stripe.git@master'
        break

# Write the updated pyproject.toml back to file
with open('/pretix/pyproject.toml', 'w') as f:
    toml.dump(pyproject, f)
