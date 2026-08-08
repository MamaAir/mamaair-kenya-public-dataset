# MamaAir WQ1 Streaming Data Format

## Overview

The MamaAir WQ1 dataset includes a streaming schema (`mamaair_stream_event.schema.json`) designed for real-time
data delivery through Amazon Kinesis Data Streams. Each event represents a single daily record from the 75
synthetic maternal health trajectories.

## Event Structure

| Field | Description |
|---|---|
| `schema_version` | Fixed `"1.0.0"` |
| `event_id` | SHA-256 of the canonical JSON record |
| `dataset_id` | `"mamaair-ssa-climate-maternal-wq1"` |
| `track_id` | `"WQ1-001"` through `"WQ1-075"` |
| `gestation_week` | 1-40 |
| `day_of_week` | 1-7 |
| `cumulative_pregnancy_day` | 1-280 |
| `source_sequence` | 0-based ordering within the dataset |
| `replay_iteration` | 0-based cycle counter |
| `replay_emitted_at` | ISO 8601 UTC timestamp |
| `replay_metadata` | Fixed payload: `kind: synthetic_dataset_replay`, `is_replay: true` |
| `trajectory_context` | Snapshot of the static profile and trajectory overview |
| `payload` | Daily record from the dataset, including `rules_engine_daily` and `quality_flags` |

## Kinesis Stream

The dataset is designed to be streamed through Amazon Kinesis Data Streams. The `track_id` field serves as the
partition key for the Kinesis stream, ensuring that all daily records for a given trajectory are delivered in
order.

## Schema Location

The streaming event schema is available at:
`releases/v1/schema/mamaair_stream_event.schema.json`
