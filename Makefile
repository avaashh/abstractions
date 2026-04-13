.PHONY: clean

server: server/venv
	@server/venv/bin/python3 server/app.py

server/venv/.complete: server/requirements.txt
	@./setup.sh
	@touch $@

server/venv: server/venv/.complete

clean:
	rm -rf server/venv
	rm -rf server/detected_images/*
