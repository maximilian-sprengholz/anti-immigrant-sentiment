.PHONY: checksetup analysis docs

checksetup:
	conda info --envs \
	&& echo $$(which python)

crawl_tripadvisor:
	python src/crawler_googlemaps.py
	
crawl_googlemaps:
	python src/crawler_googlemaps.py

analysis:

docs:

all: analysis docs
