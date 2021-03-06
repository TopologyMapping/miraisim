lint:
	pycodestyle --config rc/pycodestyle.rc *.py
	pylint3 --rcfile rc/pylint.rc *.py

test:
	coverage run -m unittest discover --start-directory tests
	coverage report

all: lint test

clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	rm -rf build dist pdns_dyndns.egg-info
