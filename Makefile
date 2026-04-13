.PHONY: server clean

server:
	@server/venv/bin/python3 server/app.py

clean:
	rm -rf server/venv
	rm -rf server/detected_images/*
