FROM xiaozhi-aipet-server:v0.9.6-b13
USER root
WORKDIR /srv/music
RUN python -m pip install --no-cache-dir fastmcp==2.13.0.2 mcp==1.20.0 python-dotenv==1.2.1
COPY server/ /srv/music/
COPY http_entry.py /srv/music/http_entry.py
USER 65534:65534
CMD python http_entry.py
