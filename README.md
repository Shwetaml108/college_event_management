# Campus Events

A lightweight college event-management app for discovering campus activities, publishing events, and managing student RSVPs. The responsive interface supports category filtering and search; event organizers can create, edit, or remove listings. Data is stored in SQLite and survives container restarts.

## Run locally

Requires Python 3.10 or newer; no third-party packages are needed.

```bash
python3 app.py
```

Open [http://localhost:8000](http://localhost:8000). The app seeds a few sample events on first launch. By default, the database is `data/events.db`; set `EVENTS_DB` to change its location.

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

## Run with Docker Compose

Build and start the application:

```bash
docker compose up --build -d
docker compose ps
```

Visit [http://localhost:8000](http://localhost:8000). Compose stores the SQLite database in the named `campus-events-data` volume.

### Container lifecycle demonstration

Stop the running container without removing it:

```bash
docker compose stop campus-events
docker compose ps -a
```

Start the same stopped container again (the named database volume is retained):

```bash
docker compose start campus-events
docker compose ps
```

Stop and remove the container and Compose network:

```bash
docker compose down
docker compose ps -a
```

`docker compose down` retains the named volume, so event data is available the next time you run `docker compose up -d`. To also permanently remove the database volume, use `docker compose down --volumes`.

The equivalent individual Docker commands are:

```bash
docker build -t campus-events .
docker run -d --name campus-events-app -p 8000:8000 \
  -v campus-events-data:/data campus-events
docker stop campus-events-app
docker start campus-events-app
docker stop campus-events-app
docker rm campus-events-app
```

The `docker rm` command removes a stopped container; the named volume remains. Use `docker volume rm campus-events-data` only when you also intend to delete its stored event data.

## Git version control

This project is maintained in Git. To record and publish your changes from a configured GitHub clone:

```bash
git add README.md app.py static/ tests/ Dockerfile compose.yaml .dockerignore
git commit -m "Build college event management app"
git push origin main
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/events?attendee_id=...` | List events, RSVP totals, and the attendee's RSVP state |
| `POST` | `/api/events` | Create an event |
| `PUT` | `/api/events/{id}` | Edit an event |
| `DELETE` | `/api/events/{id}` | Remove an event |
| `POST` | `/api/events/{id}/rsvp` | Join or leave an event with `{ "attendee_id": "...", "attending": true }` |
| `GET` | `/api/health` | Container health check |

RSVPs are unique per attendee and event; event capacity is enforced. Removing an event also removes its RSVPs.
