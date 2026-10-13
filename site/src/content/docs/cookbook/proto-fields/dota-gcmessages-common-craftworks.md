# dota_gcmessages_common_craftworks.proto

**Loaded, not used**: gem doesn't use this file, but it is imported by `dota_match_metadata.proto`, so Python loads it anyway.

- Module: `dota_gcmessages_common_craftworks_pb2`
- Imports: **4**
- Messages: **2** (top-level: 2)
- Enums: **1** (top-level: 1)

## Imports

- `steammessages.proto`
- `dota_shared_enums.proto`
- `gcsdk_gcmessages.proto`
- `google/protobuf/descriptor.proto`

## Messages

Expand any message to inspect all fields.

<details>
<summary><code>CMsgCraftworksComponents</code> — fields: 1; oneofs: 0; nested messages: 0; nested enums: 0</summary>

- Parent: *(top-level)*
- Oneofs: *(none)*

| Tag | Field | Type | Label | Oneof | Notes |
|---:|---|---|---|---|---|
| 1 | `component_quantities` | `map<uint32, uint32>` | `unlabeled` |  | map field |

</details>

<details>
<summary><code>CMsgCraftworksQuestReward</code> — fields: 3; oneofs: 0; nested messages: 0; nested enums: 0</summary>

- Parent: *(top-level)*
- Oneofs: *(none)*

| Tag | Field | Type | Label | Oneof | Notes |
|---:|---|---|---|---|---|
| 1 | `quest_id` | `uint32` | `optional` |  | boxed_type = "CraftworksQuestID_t" |
| 2 | `reward_components` | `.CMsgCraftworksComponents` | `optional` |  |  |
| 3 | `stat_value` | `uint32` | `optional` |  |  |

</details>

## Enums

Expand any enum to inspect all values.

<details>
<summary><code>ECraftworksAuditAction</code> — values: 4</summary>

- Parent: *(top-level)*

| Name | Number |
|---|---:|
| `k_eInvalid` | 0 |
| `k_eRecipeCrafted` | 1 |
| `k_eMatchRewards` | 2 |
| `k_eMatchRewardsTurbo` | 3 |

</details>
