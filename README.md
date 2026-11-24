# NYC 311 Data Pipeline

A dockerized Python pipeline that ingests NYC 311 Service Requests from the
NYC Open Data (Socrata) API, validates and cleans them, and loads them into
PostgreSQL using a bronze / silver / gold (medallion) structure, with
analytical SQL on top.

## Team

| Name | Role |
|---|---|
| Murad Huseynov | _TBD_ |
| Royal Esgerov | _TBD_ |
| Sahin Bedelov | _TBD_ |

## Quick start

> TODO: fill in once docker-compose works

    cp .env.example .env
    docker compose up --build

## Architecture

> TODO: diagram (Mermaid works natively on GitHub)

## Data model

> TODO: bronze, silver, gold tables + ERD, SCD2 dimension description

## Data quality rules

> TODO: table of rule name, description, action (quarantine / fail run)

## Idempotency and resumability

> TODO: how reruns produce identical results, how checkpoints work

## Backfill and incremental runs

> TODO: CLI examples for --mode incremental and --mode backfill

## Failure and recovery demos

> TODO: killed container, DB not ready, malformed batch (logs/screenshots)

## Git workflow and exercises

> TODO: branching model, review process, and the Git exercises we did

## Performance report

> TODO: link to docs/performance_report.md