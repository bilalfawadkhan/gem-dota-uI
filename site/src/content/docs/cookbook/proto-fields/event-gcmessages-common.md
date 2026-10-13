# event_gcmessages_common.proto

**Loaded, not used**: gem doesn't use this file, but it is imported by `dota_shared_enums.proto`, so Python loads it anyway.

- Module: `event_gcmessages_common_pb2`
- Imports: **1**
- Messages: **4** (top-level: 4)
- Enums: **1** (top-level: 1)

## Imports

- `google/protobuf/descriptor.proto`

## Messages

Expand any message to inspect all fields.

<details>
<summary><code>CMsgEventAction</code> — fields: 2; oneofs: 0; nested messages: 0; nested enums: 0</summary>

- Parent: *(top-level)*
- Oneofs: *(none)*

| Tag | Field | Type | Label | Oneof | Notes |
|---:|---|---|---|---|---|
| 1 | `action_id` | `uint32` | `optional` |  |  |
| 2 | `times_completed` | `uint32` | `optional` |  | default = 1 |

</details>

<details>
<summary><code>CMsgUserEventPoints</code> — fields: 9; oneofs: 0; nested messages: 0; nested enums: 0</summary>

- Parent: *(top-level)*
- Oneofs: *(none)*

| Tag | Field | Type | Label | Oneof | Notes |
|---:|---|---|---|---|---|
| 1 | `account_id` | `uint32` | `optional` |  |  |
| 2 | `event_id` | `uint32` | `optional` |  |  |
| 3 | `total_points` | `uint32` | `optional` |  |  |
| 4 | `total_premium_points` | `uint32` | `optional` |  |  |
| 5 | `points` | `uint32` | `optional` |  |  |
| 6 | `premium_points` | `uint32` | `optional` |  |  |
| 7 | `completed_actions` | `.CMsgEventAction` | `repeated` |  |  |
| 8 | `owned` | `bool` | `optional` |  |  |
| 9 | `active_season_id` | `uint32` | `optional` |  | boxed_type = "EventSeasonID_t" |

</details>

<details>
<summary><code>CMsgPeriodicResourceKey</code> — fields: 3; oneofs: 0; nested messages: 0; nested enums: 0</summary>

- Parent: *(top-level)*
- Oneofs: *(none)*

| Tag | Field | Type | Label | Oneof | Notes |
|---:|---|---|---|---|---|
| 1 | `account_id` | `uint32` | `optional` |  |  |
| 2 | `periodic_resource_id` | `uint32` | `optional` |  | boxed_type = "PeriodicResourceID_t" |
| 3 | `timestamp` | `uint32` | `optional` |  |  |

</details>

<details>
<summary><code>CMsgPeriodicResourceValue</code> — fields: 2; oneofs: 0; nested messages: 0; nested enums: 0</summary>

- Parent: *(top-level)*
- Oneofs: *(none)*

| Tag | Field | Type | Label | Oneof | Notes |
|---:|---|---|---|---|---|
| 1 | `periodic_resource_max` | `uint32` | `optional` |  |  |
| 2 | `periodic_resource_used` | `uint32` | `optional` |  |  |

</details>

## Enums

Expand any enum to inspect all values.

<details>
<summary><code>EEventActionScoreMode</code> — values: 2</summary>

- Parent: *(top-level)*

| Name | Number |
|---|---:|
| `k_eEventActionScoreMode_Add` | 0 |
| `k_eEventActionScoreMode_Min` | 1 |

</details>
