# The Answering Machine

A multi-agent system that talks to kids, finds them library books, and keeps parents in the loop.

## How It Works

A kid picks up a dedicated phone and talks to an AI agent about whatever's on their mind — dinosaurs, space, how cars work. The system listens, figures out what they're curious about, finds relevant books at the local library, places holds, and calls the parent to let them know what's ready for pickup.

## Architecture

```
 Kid picks up phone
        |
        v
 +-----------------+       +------------------+
 | Standard Voice  |       | 67 Mode Voice    |
 | Agent           |       | Agent            |
 | (kid-facing)    |       | (private, no     |
 |                 |       |  summaries)       |
 +--------+--------+       +------------------+
          |
          | transcripts + summaries
          v
 +--------+--------+
 | Background      |
 | Agent           |
 | - search SFPL   |
 | - place holds   |
 | - sync statuses |
 +--------+--------+
          |
          | books ready
          v
 +--------+--------+
 | Parent Agent    |
 | (outbound call) |
 | "Hey, 3 books   |
 |  are ready..."  |
 +-----------------+
```

## Repos

| Repo | What | Status |
|------|------|--------|
| [the-answering-machine](https://github.com/TDaltonC/the-answering-machine) | Project home, Background Agent, orchestration | Active |
| [updating-parents](https://github.com/TDaltonC/updating-parents) | Parent Agent (Cartesia Line) | Active |
| [answer-agent](https://github.com/TDaltonC/answer-agent) | Standard Voice Agent (Cartesia Line) | Not yet built |
| [private-agent](https://github.com/TDaltonC/private-agent) | 67 Mode Voice Agent (Cartesia Line) | Not yet built |

## This Repo

The Background Agent pipeline + orchestration:

```
main.py             — search SFPL for books based on kid's interests
hold.py             — log into SFPL and place holds on recommended books
sync_holds.py       — check hold statuses and update records
notify_parent.py    — write context to Firestore and trigger parent call
config.py           — family config from Firestore
firestore_client.py — shared Firestore client init
parsing.py          — shared book-parsing regex
```

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uvx browser-use install
```

Copy `.env.example` to `.env` and fill in your values:

```
ANTHROPIC_API_KEY=your-api-key
SFPL_USERNAME=your-library-card-number
SFPL_PASSWORD=your-pin
CARTESIA_API_KEY=your-cartesia-api-key
CARTESIA_AGENT_ID=your-agent-id
PHONE_NUMBER=+1XXXXXXXXXX
```

You also need a `service-account.json` for Firestore access (not committed).

## Usage

Run each step of the pipeline:

```bash
# 1. Search SFPL for books matching the kid's interests
uv run main.py

# 2. Place holds on the recommended books
uv run hold.py

# 3. Check hold statuses
uv run sync_holds.py

# 4. Call the parent about books ready for pickup
uv run notify_parent.py
```

## Firestore Data Model

Project: `o-phone-c0b25`

- **`families/{family_id}`** — family config (parent name, child name/age, preferred branch, phone)
- **`families/{family_id}/transcripts/{id}`** — conversation logs from voice agents
- **`families/{family_id}/summaries/{id}`** — AI-generated summaries of conversations
- **`families/{family_id}/recommendations/{id}`** — books with status tracking (recommended → hold_placed → in_transit → ready → picked_up)
- **`pending_calls/{phone}`** — context staging for outbound parent calls
