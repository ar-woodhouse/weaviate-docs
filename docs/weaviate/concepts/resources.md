---
title: Resource Planning
sidebar_position: 90
description: "CPU, memory, and GPU resource planning guidelines for optimal Weaviate performance at scale."
image: og/docs/concepts.jpg
# tags: ['architecture', 'resource', 'cpu', 'memory', 'gpu']
---

Plan resources from your workload, not an object-count threshold. Vector dimensions, named vectors, multi-vector embeddings, index settings, shards and replicas all affect resource requirements. Even a collection with fewer than 1M objects can exceed a small machine's memory or disk capacity. Depending on the modules you use, GPUs may also play a role.


## Limit available resources

You can set [environment variables](/deploy/configuration/env-vars/index.md) to manage Weaviate's resource usage, as to prevent Weaviate from using all available resources. The following environment variables are available:

- [`LIMIT_RESOURCES`](/deploy/configuration/env-vars/index.md#LIMIT_RESOURCES): When set to true, Weaviate automatically limits its resource usage. It sets memory usage to 80% of the total memory and uses all but one CPU core. It overrides any `GOMEMLIMIT` values but respects `GOMAXPROCS` settings.

- [`GOMEMLIMIT`](/deploy/configuration/env-vars/index.md#GOMEMLIMIT): This sets the memory limit for the Go runtime, which should be around 80-90% of the total memory available for Weaviate. It controls the aggressiveness of the Garbage Collector as memory usage approaches this limit.

- [`GOMAXPROCS`](/deploy/configuration/env-vars/index.md#GOMAXPROCS): This sets the maximum number of threads for concurrent execution. If set, it's respected by `LIMIT_RESOURCES`, allowing users to specify the exact number of CPU cores Weaviate should use.

These settings help in optimizing Weaviate's performance by balancing resource utilization with the available system resources.


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
Memory requirements depend on the index type and workload. When a query needs data that is not cached in memory, disk reads can affect latency.
:::

HNSW keeps its graph in memory and caches vector data separately. A cache miss can require a disk read. [Quantization](./vector-quantization.md) reduces the cached vector representation, not the graph or every other memory cost. The disk-based [HFresh index](/weaviate/concepts/vector-index#hfresh-index) has a different memory model; see [vector index types](/weaviate/concepts/vector-index).

For an uncompressed single-vector HNSW index, [`vectorCacheMaxObjects`](../config-refs/indexing/vector-index.mdx) controls the configured vector cache size, not total process memory. It does not limit graph memory, cache bookkeeping or other allocations, so it is not an out-of-memory safeguard.

Weaviate also uses [memory-mapped files](https://en.wikipedia.org/wiki/Memory-mapped_file) for data stored on disks. Memory-mapped files are efficient, but disk storage is much slower than in-memory storage.

### Which factors drive memory usage?

For an HNSW collection, include the following memory costs:

- **Vector count, dimensions and representation**. Named vectors and multi-vector embeddings can store multiple vectors per object. For HNSW without MUVERA, a multi-vector index caches component vectors. With [MUVERA](../configuration/compression/multi-vectors.md#muvera-encoding), it caches the encoded vectors instead and reads original component vectors for rescoring. Size RAM for the cached representation, not both payloads. Quantized codes also have metadata and cache bookkeeping.
- **The HNSW graph**. Each node can have up to `2 * maxConnections` connections in the base layer and up to [`maxConnections`](../config-refs/indexing/vector-index.mdx) in each higher layer. Actual graph memory also depends on the number of layers, connection encoding and allocations.
- **Object and inverted index storage, and the workload**. These stores use memory for write buffers and cached or memory-mapped data. Object properties are not part of the HNSW graph, but their size and access patterns can still affect memory use.

### An example calculation

:::note
This calculation covers only uncompressed `float32` vector payload. It is not a total RAM or disk estimate. For a bounded HNSW vector cache, see [Vector Cache](#vector-cache).
:::

Start with the vector payload:

`Vector payload bytes = vector count * dimensions * 4`

For example, consider a model that has one million 384-dimensional vectors of type `float32`.

- The payload for a single vector is: `384 * 4 B = 1536 B`.

- The payload for one million vectors is: `1e6 * 1536 B = 1.536 GB`.

That is 1.536 GB of vector payload, using decimal GB. If all these vectors are cached, allow additional RAM for the graph, cache bookkeeping, storage buffers and the Go runtime. A fixed multiplier does not account for all configurations, especially low-dimensional or quantized vectors where graph overhead is a larger share.

Sum the vector payloads for each named vector. For multi-vector HNSW without MUVERA, count component vectors rather than only objects. For MUVERA, use the encoded vector dimensions when estimating the vector cache; the original component vectors remain a disk cost. For a node's RAM budget, include the shard replicas hosted on that node. For cluster capacity, include all replicas. Measure memory during representative imports and queries before choosing a production memory limit.

## Effects of garbage collection

Weaviate is written in Go, which is a garbage-collected language. This means some memory is not immediately available for reuse when it is no longer needed. The application has to wait for an asynchronous process, the garbage collector, to free up the memory. This has two distinct effects on memory use:

- [Memory overhead](#memory-overhead-for-the-garbage-collector)
- [Out-of-memory issues](#out-of-memory-issues-due-to-garbage-collection)

### Memory overhead for the garbage collector
The vector-payload calculation excludes temporary allocations and garbage-collection headroom. Imports and queries allocate additional memory, so measure peak usage under load rather than sizing only for the stored vectors.

### Out-of-Memory issues due to garbage collection
In rare situations - typically on large machines with very high import speeds - Weaviate can allocate memory faster than the garbage collector can free it. When this happens, the system kernel can trigger an `out of memory kill (OOM-Kill)`. This is a known issue that Weaviate is actively working on.

### Data import
To avoid out-of-memory issues during imports, set `LIMIT_RESOURCES` to `True` or configure the `GOMEMLIMIT` environment variable. For details, see [Environment variables](/deploy/configuration/env-vars/index.md).

## Strategies to reduce memory usage

The following tactics can help to reduce Weaviate's memory usage:

- **Use vector compression**. Product quantization (PQ) is a technique that reduces the size of vectors. Vector compression impacts recall performance, so we recommend testing PQ on your dataset before using it in production. <br/><br/> For more information, see [Product Quantization](/weaviate/concepts/vector-quantization). <br/> To configure PQ, see [Compression](../configuration/compression/pq-compression.md).

- **Consider a lower-dimensional embedding model.** Fewer dimensions reduce vector payload, not graph memory. Compare retrieval quality before changing models.

- **Choose a smaller [`maxConnections`](../config-refs/indexing/vector-index.mdx) when creating an HNSW index.** This reduces the graph's connection capacity, but can reduce recall. A higher `efConstruction` or `ef` can compensate at the cost of more work during index construction or search, respectively. Measure the resulting recall and latency.

- **Use a vector cache that is smaller than the total amount of your vectors (not recommended)**. This strategy is described under [Vector Cache](#vector-cache) below. It has a significant performance impact, and is only recommended in specific, limited situations.

## HNSW vector cache {#vector-cache}

For an uncompressed single-vector HNSW index, [`vectorCacheMaxObjects`](../config-refs/indexing/vector-index.mdx) sets the configured number of cached vectors per shard and per named vector. Its default is one trillion (`1e12`). This is a cache setting, not a byte limit on Weaviate's memory use.

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

Plan disk capacity separately from RAM. Quantization does not remove the full-precision vectors from the object store; compressed HNSW indexes also persist their quantized codes. Include object properties, inverted indexes, write-ahead logs and other index files, not just the compressed vector payload. For a node's disk budget, include its shard replicas; for cluster capacity, include all replicas.

## Disks: SSD vs Spinning Disk

Weaviate is optimized to work with Solid-State Disks (SSDs). However, spinning hard-disks can also be used with some performance penalties.

## File system

For optimal performance and reliability, avoid using `NFS` or similar file systems for the Weaviate persistent volume ([`PERSISTENCE_DATA_PATH`](/deploy/configuration/env-vars/index.md)). 

Instead, use file systems like `Ext4` or `XFS` in combination with SAN storage (e.g. `EBS`) to ensure the best performance.

## Questions and feedback

import DocsFeedback from '/_includes/docs-feedback.mdx';

<DocsFeedback/>
