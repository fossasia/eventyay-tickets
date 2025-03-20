import os

import toml

# Get the stripe_key from environment variable
github_token = os.getenv('GITHUB_TOKEN')

# Load the pyproject.toml file
pyproject = toml.load('/pretix/pyproject.toml')

# If github_token is None, remove the eventyay-stripe and eventyay-paypal dependency
if not github_token:
    pyproject['project']['dependencies'] = [
        dep for dep in pyproject['project']['dependencies'] if not dep.startswith('eventyay-stripe')
    ]
    pyproject['project']['dependencies'] = [
        dep
        for dep in pyproject['project']['dependencies']
        if not (dep.startswith('eventyay-stripe') or dep.startswith('eventyay-paypal'))
    ]
else:
    # Iterate over the dependencies
    for i, dep in enumerate(pyproject['project']['dependencies']):
        if dep.startswith('eventyay-stripe'):
            # Update the stripe dependency with the github_token
            pyproject['project']['dependencies'][i] = (
                f'eventyay-stripe @ git+https://{github_token}@github.com/fossasia/eventyay-tickets-stripe.git@master'
            )
        elif dep.startswith('eventyay-paypal'):
            # Update the PayPal dependency with the github_token
            pyproject['project']['dependencies'][i] = (
                f'eventyay-paypal @ git+https://{github_token}@github.com/fossasia/eventyay-tickets-paypal.git@master'
            )

# Write the updated pyproject.toml back to file
with open('/pretix/pyproject.toml', 'w') as f:
    toml.dump(pyproject, f)
