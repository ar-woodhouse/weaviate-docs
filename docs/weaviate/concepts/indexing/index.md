---
title: Indexing
sidebar_position: 0
description: "Overview of Weaviate's indexing systems for optimized search performance and data retrieval efficiency."
image: og/docs/concepts.jpg
# tags: ['basics']
---

Weaviate uses three kinds of index, and you configure them per collection.

| Index | Answers | Details |
| :---- | :------ | :------ |
| [Vector index](./vector-index.md) | Which objects are closest in vector space? | [Vector index reference](../../config-refs/indexing/vector-index.mdx) |
| [Inverted index](./inverted-index.md) | Which objects match this filter or keyword? | [Inverted index reference](../../config-refs/indexing/inverted-index.mdx) |
| [Compression](../vector-quantization.md) | How much memory and disk does each vector cost? | [Compression configuration](../../configuration/compression/index.md) |

Weaviate has four vector index types:

- **HNSW**: an approximate nearest neighbor (ANN) graph index held in memory. Scales well to large datasets.
- **HFresh**: a cluster-based index that keeps only a compressed centroid index in memory and stores the rest on disk.
- **Flat**: a brute-force, disk-based index. Good for small datasets and for isolated tenants.
- **Dynamic**: a flat index that converts to HNSW when the object count crosses a threshold.

To choose, read the [comparison between index types](./vector-index.md#comparison-between-index-types) and the [indexing recommendations](../../starter-guides/managing-resources/indexing.mdx#vector-indexes). Then pick a [quantizer](../vector-quantization.md).

## Changing an index later

| Change | What happens |
| :----- | :----------- |
| Add or widen a quantizer (BQ, PQ, SQ or RQ) | Accepted on an existing collection. Weaviate re-encodes the stored vectors in the background. |
| Change HFresh tuning (`searchProbe`, `rq.rescoreLimit`) | Accepted and applied without reindexing. |
| Change the vector index type (`hnsw`, `flat`, `dynamic`, `hfresh`) | Not possible. Create a new collection and [migrate the data](../../manage-collections/migrate.mdx). |
| Add a property, or change its inverted index settings | Accepted. Existing objects are not indexed for the new setting until you rebuild the index. See [Inverted index](../../config-refs/indexing/inverted-index.mdx). |
| Change tokenization or accent folding on a `text` property | Accepted for new objects only. Existing objects keep the tokens they were indexed with. |

:::tip Tips for indexing

Especially for large datasets, configuring the indexes is important because the more you index, the more storage is needed. A rule of thumb - if you don't query over a specific field or vector space, don't index it.

:::
