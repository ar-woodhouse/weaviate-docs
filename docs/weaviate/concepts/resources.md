---
title: Resource Planning
sidebar_position: 90
description: "CPU, memory, and GPU resource planning guidelines for optimal Weaviate performance at scale."
image: og/docs/concepts.jpg
# tags: ['architecture', 'resource', 'cpu', 'memory', 'gpu']
---

Weaviate scales well for large projects. Plan resources from the vectors you store and the indexes that hold them, not from an object count. Vector dimensions, named vectors, multi-vector embeddings, index settings, compression, shards and replicas all change the requirement, so a collection with fewer than 1M objects can still exceed the memory or disk of a small instance.

CPU and memory are the primary resources for Weaviate instances. Depending on the modules you use, GPUs may also play a role.


## Limit available resources

You can set [environment variables](/deploy/configuration/env-vars/index.md) to manage Weaviate's resource usage, as to prevent Weaviate from using all available resources. The following environment variables are available:

- [`LIMIT_RESOURCES`](/deploy/configuration/env-vars/index.md#LIMIT_RESOURCES): When set to true, Weaviate automatically limits its resource usage. It sets memory usage to 80% of the total memory and uses all but one CPU core. It overrides any `GOMEMLIMIT` values but respects `GOMAXPROCS` settings.

- [`GOMEMLIMIT`](/deploy/configuration/env-vars/index.md#GOMEMLIMIT): This sets the memory limit for the Go runtime, which should be around 80-90% of the total memory available for Weaviate. It controls the aggressiveness of the Garbage Collector as memory usage approaches this limit.

- [`GOMAXPROCS`](/deploy/configuration/env-vars/index.md#GOMAXPROCS): This sets the maximum number of threads for concurrent execution. If set, it's respected by `LIMIT_RESOURCES`, allowing users to specify the exact number of CPU cores Weaviate should use.

These settings help in optimizing Weaviate's performance by balancing resource utilization with the available system resources.

Set `GOMEMLIMIT`, or set `LIMIT_RESOURCES` to `true`, on production instances. Without a soft memory limit, Weaviate cannot act on its internal memory-pressure checks, such as batch admission and vector index growth, and it logs a warning at startup.

`GOMEMLIMIT` is a soft budget for the Go runtime, not an operating-system limit. It makes the garbage collector work harder as the Go heap approaches the limit, and it is the value that Weaviate's admission checks compare against. Memory-mapped file pages and the kernel page cache are outside the Go heap, so they are not bounded by this setting. Size the container for the mapped data and for the rest of the process, and treat `GOMEMLIMIT` as a heap budget that reduces, but does not remove, out-of-memory risk.


## The role of CPUs

:::tip Rule of thumb
The CPU has a direct effect on query and import speed, but does not affect dataset size.
:::

Vector search is the most CPU intensive process in Weaviate operations. Queries are CPU-bound, but imports are also CPU-bound because imports rely on vector search for indexing. Weaviate uses the HNSW (Hierarchical Navigable Small World) algorithm to index vectors. You can [tune the HNSW index](../config-refs/indexing/vector-index.mdx) on a per collection basis in order to maximize performance for your primary use case.

To use multiple CPUs efficiently, create multiple shards for your collection. For the fastest imports, create multiple shards even on a single node.

Each insert, or search, is single-threaded. However, if you make multiple searches or inserts at the same time, Weaviate can make use of multiple threads. [Batch inserts](/weaviate/manage-objects/import) use multiple threads to process data in parallel.

### When to add more CPUs

When CPU utilization is high during importing, add CPUs to increases import speed.

When search throughput is limited, add CPUs to increase the number of queries per second.

## The role of memory

:::tip Rule of thumb
Memory sets how much vector data and index structure a node can keep in memory. Query speed depends on the index type, and on whether a query finds the vectors it needs in memory.
:::

An HNSW index keeps its graph in memory and caches vector data separately. A query that misses the vector cache reads the vector from disk, which is much slower than a memory lookup. [Quantization](./vector-quantization.md) changes the representation that the index caches and scores. It does not reduce the graph. The full-precision vector stays in the object store, which is also where rescoring reads it from.

The disk-based [HFresh index](./indexing/vector-index.md#hfresh-index) uses a different layout. It keeps an HNSW index over cluster centroids in memory, and it keeps posting metadata in memory: the posting map records which vector IDs belong to each posting. The posting lists themselves are on disk. Its memory therefore depends on the centroid vectors and their graph, on the posting assignments, and on buffers and page cache. It does not cache every vector.

For an uncompressed HNSW index, [`vectorCacheMaxObjects`](../config-refs/indexing/vector-index.mdx) sets the size of the vector cache, per shard and per named vector. Its default is one trillion (`1e12`) entries. The count is vector entries, not objects: a multi-vector index without MUVERA caches one entry per component vector. The cache fills as vectors are imported or read, so the value is a cap, not a reservation. It does not limit the graph, the object store, write buffers or the Go heap.

Compressed indexes cache codes instead. The quantizer path that creates those caches does not always size them from this setting, and a `flat` index uses the setting only for its optional BQ or RQ code cache. Do not read `vectorCacheMaxObjects` as a byte limit or as a hard cap on every cache. For a budget for the Go runtime, see [`GOMEMLIMIT`](#limit-available-resources).

Weaviate also uses [memory-mapped files](https://en.wikipedia.org/wiki/Memory-mapped_file) for data stored on disks. Memory-mapped files are efficient, but disk storage is much slower than in-memory storage.

### Which factors drive memory usage?

For an HNSW collection, size these components separately:

- **Vector payload.** A `float32` vector uses `4 * dimensions` bytes. Count each named vector. For a multi-vector embedding without MUVERA, count every component vector, because the index caches and indexes them individually. With [MUVERA](../configuration/compression/multi-vectors.md#muvera-encoding), the cache holds the encoded vector instead: by default that vector has 2,560 dimensions, about 10 kB in `float32`, and the component vectors stay in the object store.
- **Quantized codes.** With BQ, PQ, SQ or RQ, the index caches compressed codes instead of `float32` vectors. The code size depends on the representation and not only on the dimension count: 8-bit RQ uses about 1 byte per dimension after rounding the dimension count up to a multiple of 64, plus 16 bytes per vector. Compression reduces the cached entry, not the graph.
- **The HNSW graph.** Every indexed vector has a layer-zero entry with up to `2 * maxConnections` connections, and up to [`maxConnections`](../config-refs/indexing/vector-index.mdx) connections in each higher layer. Without MUVERA, a multi-vector index has a graph node for each component vector. A stored connection is an internal node ID of 2, 3, 4, 5 or 8 bytes, depending on the ID range. Node structs, the per-node connection header and allocator overhead add further cost that this per-link figure does not include.
- **Objects, inverted indexes and queues.** Object properties, inverted indexes, the write-ahead log and the async index queue live on disk, and use memory for write buffers and memory-mapped pages. They are not part of a vector estimate.
- **Shards and replicas.** Each shard has its own index, and each named vector has its own index within a shard. Each database replica is a full copy of a shard, hosted on another node.

Size one shard first, then add the replicas that a node hosts, and only then sum the cluster. Do not divide a cluster figure by the node count without checking the shard placement.

### An example calculation

:::note
This example estimates vector payload, 8-bit RQ code size and the packed layer-zero link payload. It is not a total RAM or disk figure: it leaves out the rest of the graph, runtime overhead, write buffers and garbage-collection headroom. See [Measure before you change](#measure-before-you-change).
:::

Consider one million objects with one named `float32` vector of 1,536 dimensions in one collection.

- Vector payload: `1e6 * 1536 * 4 B = 6.144 GB`, using decimal GB.
- The same vectors with 8-bit RQ: about `1536 B + 16 B = 1.552 kB` per vector, so `1.552 GB` of codes. 1,536 is already a multiple of 64, so no padding applies here.
- Packed layer-zero links only: at the default `maxConnections` of 32, with every layer-zero list full at 64 entries and 3 bytes per node ID (an ID range above 65,535 and below 16,777,216), up to `1e6 * 64 * 3 B = 0.192 GB`. This excludes upper layers, node structs, the connection headers and allocator overhead, so it is not the graph's RAM use.

In this example the payload dominates an uncompressed index. Compression reduces the payload, so the graph and the code metadata become a larger share of the index after compression. For low-dimensional vectors the graph is already a significant share.

Each shard holds roughly its share of the payload, but do not divide the link figure by the shard count: each shard's index has its own ID range, so the encoding width can differ. For a node's budget, add every shard replica that the node hosts. For a cluster budget, include every replica: with a replication factor of 2 on two nodes, each node can host one replica of each shard, so each node needs room for the whole collection.

One million vectors hold `4.096 GB` at 1,024 dimensions and `1.536 GB` at 384 dimensions. Fewer input dimensions always reduce the `float32` payload. They do not reduce every code representation in proportion: PQ code bytes depend on `segments`, BQ pads to whole 64-bit blocks, RQ pads the dimension count to a multiple of 64, and MUVERA encodes to its own configured dimension.

## Choose a starting configuration

Use these starting points, then confirm them with the measurements below.

| Starting point | Reason to choose it | What it costs |
| --- | --- | --- |
| `hnsw`, no compression | The payload and graph fit the container with room for import peaks. It has no compression step, so only the graph approximates the result. | The index caches full `float32` vectors and keeps the graph in memory. |
| `hnsw` with 8-bit RQ | Vector payload dominates memory. 8-bit RQ needs no training data. | About 1 byte per dimension after padding to a multiple of 64, plus 16 bytes per vector, and approximate compressed distances. Keep [rescoring](./vector-quantization.md#over-fetching--re-scoring) enabled until you measure its effect. |
| `hnsw` with 4-bit RQ, 1-bit RQ, BQ, PQ or SQ | One of these representations fits your data or your memory budget better than 8-bit RQ. 4-bit RQ applies to the HNSW index implementation, which includes the HNSW stage of a dynamic index. PQ and SQ need training data; 4-bit RQ needs it only with `centering`; BQ depends on the model. | Code size and distance accuracy depend on the bit width, the padding and your data. Measure [top-k overlap with exact search](#measure-ann-recall) at the `limit` you serve. |
| `flat` | A collection or tenant stays small enough that a brute-force scan meets the latency target. It has no HNSW graph. | A query scans the eligible vectors, so filters, the optional BQ or RQ code cache, vector dimensions and storage read speed drive the latency. |
| `dynamic` | Many collections or tenants start small and some may grow. | The index is [experimental](./indexing/vector-index.md#dynamic-index) and requires async indexing. It converts from flat to HNSW only, and it does not support multi-vector embeddings. |
| `hfresh` | An HNSW index does not fit the memory budget. | `cosine` and `l2-squared` only. A query traverses the centroid index and reads posting lists from disk, and the vector `replicas` setting (not the database replication factor) controls how many posting lists each vector is assigned to. |

Reconsider the choice when any of these occurs:

- Peak memory during a representative import approaches the container limit or `GOMEMLIMIT`.
- Measured top-k overlap with exact search is below your target at the `limit` you serve.
- p95 or p99 latency, or throughput, misses the target at production concurrency and with production filters.
- The disk budget is exceeded when you include full-precision vectors, compressed codes and every replica.
- You need dot product distance, which `hfresh` does not support.
- You need multi-vector embeddings without MUVERA. `flat` and `dynamic` do not support multi-vector embeddings, and `hfresh` requires MUVERA encoding. See [Multi-vector embeddings](../configuration/compression/multi-vectors.md#muvera-encoding) for which index and encoding combinations are supported.
- Deletions and updates dominate the workload.

## Measure before you change

A single measurement round answers most of the questions above.

### Measure ANN recall

Approximate nearest neighbor (ANN) recall measures how closely an approximate index reproduces an exact search. To measure it, create a reference collection with the same objects, vectors, distance metric and filters, with a `flat` index and no quantizer. A reference that inherits a quantizer measures compression, not the graph. Query both collections with the same queries and the same `limit`, then compare the returned IDs:

`recall = (number of IDs in both result sets) / (size of the exact result set)`

This recipe covers an ordinary single-vector embedding. `flat` and `dynamic` do not accept multi-vector embeddings, so a multi-vector workload, encoded with MUVERA or not, has no comparable exact reference in this recipe, and this page provides no verified ANN-overlap procedure for it. End-to-end relevance measurement is a different check: it does not measure how closely an index reproduces an exact search, so it does not replace ANN overlap.

The exact search sets the denominator. If it returns fewer than `limit` objects, for example because a filter excludes the rest, divide by the number it returns, not by `limit`. If it returns nothing, there is no reference result to compare: check the import, the filters and async catch-up before you interpret the query. Results at equal distances can come back in a different order, so expect the overlap to vary a little when a query has ties at the cutoff.

This measures index approximation only. It does not measure whether the returned objects answer the user's question, which depends on the embedding model and your evaluation of relevance. A query whose candidate set is smaller than [`flatSearchCutoff`](../config-refs/indexing/vector-index.mdx) is answered by a direct scan instead of a graph traversal. That scan does not exercise the graph, but on a compressed index it still uses the compressed distances and any rescoring, so it is not a full-precision exact reference. See [Flat-search cutoff](./filtering.md#flat-search-cutoff).

If the instance sets [`DEFAULT_QUANTIZATION`](/deploy/configuration/env-vars/index.md#DEFAULT_QUANTIZATION), keep the reference uncompressed. In Python, pass `quantizer=Configure.VectorIndex.Quantizer.none()`, which sets `skipDefaultQuantization`. Over REST, add `"skipDefaultQuantization": true` to the `vectorIndexConfig` of the reference collection:

```json
{
  "class": "RefFlat",
  "vectorizer": "none",
  "vectorIndexType": "flat",
  "vectorIndexConfig": { "distance": "cosine", "skipDefaultQuantization": true }
}
```

With [async indexing](./indexing/vector-index.md#asynchronous-indexing) enabled, a collection can return no vector results until its index catches up. Wait for the import queue to drain before you compare results. The [compression guide](../starter-guides/managing-resources/compression.mdx#recall) includes a Python example.

### Measure peak memory and disk

- Import a representative batch and watch the container RSS and the `go_memstats_heap_inuse_bytes` metric. Note the difference to `GOMEMLIMIT`.
- Measure the data directory size per shard before and after a compression change, and include every replica that the node hosts.
- Run production-shaped queries, with the filters, `limit` and concurrency you expect, and record p50, p95, p99 latency and queries per second. A single-query timing does not show contention or disk reads.

See [Best practices: how to check memory usage](../best-practices/index.md#how-to-quickly-check-the-memory-usage) for the available tools and their limits.

## Effects of garbage collection

Weaviate is written in Go, which is a garbage-collected language. This means some memory is not immediately available for reuse when it is no longer needed. The application has to wait for an asynchronous process, the garbage collector, to free up the memory. This has two distinct effects on memory use:

- [Memory overhead](#memory-overhead-for-the-garbage-collector)
- [Out-of-memory issues](#out-of-memory-issues-due-to-garbage-collection)

### Memory overhead for the garbage collector
The estimates on this page describe the system at rest. While Weaviate imports vectors, additional memory is allocated and eventually freed by the garbage collector. Because garbage collection is an asynchronous process, peak memory can exceed the stored-data estimate. Measure peak usage during a representative import rather than adding a fixed percentage to a stored-data estimate.

### Out-of-Memory issues due to garbage collection
In rare situations - typically on large machines with very high import speeds - Weaviate can allocate memory faster than the garbage collector can free it. When this happens, the system kernel can trigger an `out of memory kill (OOM-Kill)`. This is a known issue that Weaviate is actively working on.

### Data import
To reduce the risk of out-of-memory issues during imports, set `LIMIT_RESOURCES` to `true` or configure `GOMEMLIMIT`, and give the container room for memory-mapped data. For details, see [Environment variables](/deploy/configuration/env-vars/index.md).

## Strategies to reduce memory usage

The following tactics can help to reduce Weaviate's memory usage:

- **Use vector compression**. [Rotational quantization (RQ)](./vector-quantization.md#rotational-quantization) needs no training data in its 8-bit and 1-bit forms; 4-bit RQ needs training only with `centering`. Product quantization (PQ) always needs training data per shard. Compression changes recall, so [measure it](#measure-ann-recall) on your dataset before you use it in production. <br/><br/> For the available techniques, see [Vector quantization](./vector-quantization.md). <br/> To configure compression, see [Compression](../starter-guides/managing-resources/compression.mdx).

- **Reduce the dimensionality of your vectors.** Fewer dimensions reduce the `float32` payload, and the graph does not change. The code size shrinks by a different amount: PQ code bytes depend on `segments`, and RQ and BQ pad the dimension count. A different model also changes the vectors themselves, so compare retrieval quality before you switch. For example, a model with 384 dimensions uses far less payload than a model with 1,536 dimensions.

- **Reduce [`maxConnections`](../config-refs/indexing/vector-index.mdx) when you create the HNSW index.** Each indexed vector has up to `2 * maxConnections` connections in layer zero, and each connection is an internal node ID of 2 to 8 bytes. A smaller `maxConnections` reduces graph memory, and it can reduce recall.

  To mitigate the recall effect, increase `ef`. `efConstruction` is a create-time setting, so a higher value requires a new index or a new collection. It changes what the index builds: a higher value builds a better-connected graph, which can reduce the search work that a given `ef` needs, at the cost of slower imports. A higher `ef` increases the work per query. Measure both effects on your data.

- **Use a vector cache that is smaller than the total amount of your vectors (not recommended)**. This strategy is described under [Vector Cache](#vector-cache) below. It has a significant performance impact, and is only recommended in specific, limited situations.

## Vector Cache

For optimal search and import performance, previously imported vectors need to be held in memory. For an uncompressed HNSW index, the vector cache is configured by [`vectorCacheMaxObjects`](../config-refs/indexing/vector-index.mdx) in the collection definition, for each shard and each named vector. By default the limit is one trillion (`1e12`) vector entries, and it counts component vectors of a multi-vector embedding, not objects.

You can reduce the size of `vectorCacheMaxObjects`, but a disk lookup for a vector is orders of magnitudes slower than memory lookup. Only reduce the size of `vectorCacheMaxObjects` with care and as a last resort.

Generally we recommend that:
- During import set `vectorCacheMaxObjects` high enough that all vectors can be held in memory. Each import requires multiple searches. Import performance drop drastically when there isn't enough memory to hold all of the vectors in the cache.

- After import, when your workload is mostly querying, experiment with vector cache limits that are less than your total dataset size.

  Vectors that aren't currently in cache are added to the cache if there is still room. If the cache fills, Weaviate drops the whole cache. All future vectors have to be read from disk for the first time. Then, subsequent queries runs against the cache, until it fills again and the procedure repeats. Note that the cache can be a very valuable tool if you have a large dataset, and a large percentage of users only query a specific subset of vectors. In this case you might be able to serve the largest user group from cache while requiring disk lookups for "irregular" queries.

### When to add more Memory to your Weaviate machine or cluster

Consider adding more memory if:
- You want to import a larger dataset (more common).
- Exact lookups are disk-bound and more memory will improve page-caching (less common).

## The role of GPUs in Weaviate

Weaviate Database itself does not make use of GPUs. However, some of the models that Weaviate includes as modules are meant to run with GPUs, for example `text2vec-transformers`, `qna-transformers`, and `ner-transformers`. These modules run in isolated containers, so you can run the module containers on GPU-accelerated hardware while running Weaviate Database on low-cost CPU-only hardware.

## Disk capacity

Vectors are written to the object store whether or not you compress them, so compression does not move data that was only in memory onto disk. It adds compressed codes to the index's own storage, and it changes what the index caches. Whether node RAM falls depends on the index type and on how much of the data the cache holds: a `flat` index without its optional code cache caches nothing per vector, so compressing it adds codes without giving back cache memory. Plan for all of these components:

- The full-precision vectors in the object store, which rescoring also reads.
- The compressed codes of every compressed index, and any codebooks or training state.
- Object properties, inverted indexes, the write-ahead log and the async index queue.
- One copy of each database shard replica that the node hosts.

Measure the data directory size for a representative sample before you set a disk limit. For the thresholds that switch Weaviate to read-only mode, see [Customize system thresholds to prevent downtime](../best-practices/index.md#customize-system-thresholds-to-prevent-downtime).

## Disks: SSD vs Spinning Disk

Weaviate is optimized to work with Solid-State Disks (SSDs). However, spinning hard-disks can also be used with some performance penalties.

## File system

For optimal performance and reliability, avoid using `NFS` or similar file systems for the Weaviate persistent volume ([`PERSISTENCE_DATA_PATH`](/deploy/configuration/env-vars/index.md)). 

Instead, use file systems like `Ext4` or `XFS` in combination with SAN storage (e.g. `EBS`) to ensure the best performance.

## Questions and feedback

import DocsFeedback from '/_includes/docs-feedback.mdx';

<DocsFeedback/>
