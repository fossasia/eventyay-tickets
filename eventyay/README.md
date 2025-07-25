# ENext

This is the new and updated version of Eventyay with unified codebase of the Tickets, Talk and Videos Components.

## Getting Started

1. Clone the repository
	```
	https://github.com/Sak1012/eventyay-tickets.git
	```

2. Create a Virtual Environment and Activate it
	```
	python -m venv venv
	source venv/bin/activate
	```

3. Install and update pip and setuptools to avoid failure of dependencies.
	```
	pip3 install -U pip setuptools
	```
4. Enter Eventyay-Tickets
	```
	cd eventyay-tickets
	```
5. Switch to Enext branch 
	```
	git switch enext 
	```
6. Enter Eventyay (Unified System)
	```
	cd eventyay
	```
 
8. Install Requirements
	```
	pip install -r requirements.txt
	```
9. Initialize the database
	```
	python manage.py migrate
	```
10. Run the server
	```
	python manage.py runserver
	```
