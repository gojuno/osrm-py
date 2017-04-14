
data/docker-osrm-backend:
	mkdir -p data
	docker pull osrm/osrm-backend:v5.6.5
	touch $@


data/new-york-latest.osm.pbf: data/docker-osrm-backend
	mkdir -p data
	wget http://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf \
		-O $@

data/new-york-latest.osrm: data/new-york-latest.osm.pbf
	docker run \
		--rm -t -v $(shell pwd)/data:/data \
		osrm/osrm-backend:v5.6.5 \
		osrm-extract -p /opt/car.lua /data/new-york-latest.osm.pbf

data/new-york-latest.osrm.core: data/new-york-latest.osrm
	docker run \
		--rm -t -v $(shell pwd)/data:/data \
		osrm/osrm-backend:v5.6.5 \
		osrm-contract /data/new-york-latest.osrm

osrm-backend: data/new-york-latest.osrm.core
	docker run \
		--name osrm-backend \
		-d -t -i -p 5000:5000 \
		-v $(shell pwd)/data:/data \
		osrm/osrm-backend:v5.6.5 \
		osrm-routed /data/new-york-latest.osrm

test:
	python setup.py test

lint:
	flake8 --ignore=F403,E501,E241 osrm.py
