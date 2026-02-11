# The Answering Machine

A multi-agent system that talks to kids, finds them library books, and keeps parents in the loop.

![Comic strip: A boy asks his dad how cement dries in the rain. Dad suggests asking the Answering Machine. The boy picks up an orange rotary phone and gets an answer. Later that week, dad gets a text about a library book and nearby construction site. The boy presses his hands into wet cement. Walking home, he asks another question.](docs/comic.jpg)

[Post about why this project exists](https://tdaltonc.github.io/the-answering-machine/)

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
| [parent-facing-agent](https://github.com/TDaltonC/parent-facing-agent) | Parent Agent (Cartesia Line) | Active |
| [answer-agent](https://github.com/TDaltonC/answer-agent) | Standard Voice Agent (Cartesia Line) | Active |
| [private-agent](https://github.com/TDaltonC/private-agent) | 67 Mode Voice Agent (Cartesia Line) | Active |

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

## Hardware

The phone is a regular analog phone connected to the internet via an ATA (Analog Telephone Adapter). The ATA converts the analog signal to SIP/VoIP and routes the call to Cartesia, which handles connecting to the right voice agent.

### Components

- **Analog phone** — any corded or cordless phone with a standard RJ11 jack
- **Grandstream HT802** — ATA that bridges the analog phone to SIP. Handles autodial, dial plan, and call routing
- **TP-Link TL-WR1502X** — portable Wi-Fi 6 travel router so the ATA doesn't need a hardline ethernet connection. Also provides a clean LAN for configuring the ATA's web interface

### What happens when the kid picks up the phone

1. The phone goes **off-hook** and the ATA detects it
2. In **hotline mode**, the ATA immediately dials the SIP number for the Standard Voice Agent — no dial tone, no waiting. The kid just picks up and starts talking
3. The ATA sends a SIP INVITE to Cartesia's Twilio trunk, which routes it to the voice agent
4. Cartesia connects the call to the Standard Voice Agent, which picks up and starts the conversation

The whole sequence takes a few seconds. To the kid, it feels like picking up a phone and someone's there.

### Dial plan

```
{ <67:[private-agent-number] | 1xxxxxxxxxx }
```

- **No digits (default)** — autodials to the Standard Voice Agent. This is the normal path for kids
- **`67`** — routes to the 67 Mode (private) agent. A kid who knows the code dials 67 before the autodial kicks in to get the private, no-summary agent
- **`1xxxxxxxxxx`** — any 11-digit number passes through as a normal call

### Autodial configuration

The HT802 supports two autodial modes:

- **Hotline** — dials instantly on off-hook. Best for single-agent mode where you want zero friction
- **Warmline** — waits a configurable delay before autodialing. Required for 67 Mode so the kid has time to punch in `67` before the default number fires

Tune the warmline delay to get the right feel. Too short and kids can't dial 67 in time. Too long and it feels like the phone is broken. The delay also affects perceived responsiveness — the call setup time on Cartesia's end adds a few more seconds on top.

## Firestore Data Model

Project: `o-phone-c0b25`

- **`families/{family_id}`** — family config (parent name, child name/age, preferred branch, phone)
- **`families/{family_id}/transcripts/{id}`** — conversation logs from voice agents
- **`families/{family_id}/summaries/{id}`** — AI-generated summaries of conversations
- **`families/{family_id}/recommendations/{id}`** — books with status tracking (recommended → hold_placed → in_transit → ready → picked_up)
- **`pending_calls/{phone}`** — context staging for outbound parent calls
