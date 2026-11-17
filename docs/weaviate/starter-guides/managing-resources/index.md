---
title: Managing resources (Hot, Warm, Cold)
description: Learn to manage resources effectively in Weaviate for optimized performance.
sidebar_position: 10
image: og/docs/tutorials.jpg
# tags: ['basics']
---

Weaviate provides flexible resource management features that help you to balance search speeds; search accuracy and recall; and system resource costs.

This guide provides an overview of these topics to help you make allocate resources effectively:

- **[Storage tiers (*hot, warm, cold*)](#storage-tiers---temperatures)**
- **[Vector index types](#vector-index-types)**
- **[Vector compression](#vector-compression)**
- **[Tenant states](#tenant-states)**
- **[Tips](#tips)**

:::tip Resource management Tips

- Start with the dynamic [index type](#vector-index-types) unless you have a reason not to.
- Consider [vector compression](#vector-compression) techniques if some loss of accuracy is acceptable.
    - This will improve query speeds.
    - For HNSW indexes, this will reduce memory usage.
- Avoid overprovisioning storage. Especially *hot* storage.
    - Can you use [tenant states](#tenant-states) to reduce costs?
    - Can you use [vector compression](#vector-compression) to reduce memory usage?

:::

## Storage Tiers - Temperatures

![Storage Tiers](./img/storage-tiers.jpg)

We categorize storage resources using three tiers: [*hot*](#-hot), [*warm*](#-warm), and [*cold*](#-cold). Each tier has different performance characteristics and costs.

| Tier     | Vector <br/> Index Type | Vector <br/> Compression | Tenant State  | Storage    | Performance           | Cost      |
|----------|-------------------|--------------------|---------------|------------|-----------------------|----------|
| 🟥 Hot   | HNSW              | PQ, SQ, BQ         | Active        | Memory | Fastest                | High     |
| 🟨 Warm  | Flat              | BQ                 | Active        | SSD       | Slower                 | Moderate |
| 🟦 Cold  | Any               | Any                | Inactive      | Cloud     | Resource not available | Low      |

### 🟥 Hot

![Storage Tiers - Hot](./img/storage-tiers-hot.jpg)

- Describes memory usage
- Fastest and most expensive
- Primarily driven by [`HNSW`](./indexing.mdx#hnsw-indexes) vector indexes
- Always available (active) for use
- Costs increase rapidly with scale

### 🟨 Warm

![Storage Tiers - Warm](./img/storage-tiers-warm.jpg)

- Describes data stored on disk (SSD)
- Slower than [hot](#-hot) tier but less expensive
- Driven by [flat](./indexing.mdx#flat-indexes) vector index, object data, and [inverted indexes](./indexing.mdx#inverted-indexes)
- Always available (active) for use
- Costs increase more slowly than hot tier as data grows

### 🟦 Cold

![Storage Tiers - Cold](./img/storage-tiers-cold.jpg)

import OffloadingLimitation from '/_includes/offloading-limitation.mdx';

<OffloadingLimitation/>

- Describes data stored in cloud storage
- Slowest and least expensive tier
- Primarily driven by [offloaded tenants](#tenant-states)
- Resources are not available (inactive) for use
- Requires [reactivation](#tenant-states) to access


## Resource Management - Key Factors

Effective resource management in Weaviate involves balancing performance, cost, and data accessibility. The key levers to manage resources are:

- **[Vector index types](#vector-index-types)**: Choose the right index type based on the number of objects and desired performance.
- **[Vector compression](#vector-compression)**: Use compression techniques to reduce memory usage and improve query performance at the cost of some accuracy.
- **[Tenant states](#tenant-states)**: Manage tenant states to balance cost and performance.

### Vector index types

The choice of vector index type can have a significant impact on performance and resource usage. Weaviate supports the following index types:

| Index Type | Resource Usage | Performance | Suitable for | Description |
|------------|----------------|-------------|--------------|-------------|
| HNSW       | 🟥 Hot         | Fast        | Any object count | A memory-based, fast index ([read more](./indexing.mdx#hnsw-indexes)) |
| Flat       | 🟨 Warm        | Medium      | Small sets, confirm latency | A disk-based, brute-force index ([read more](./indexing.mdx#flat-indexes)) |
| Dynamic    | Depends        | Depends     | Collections that start small | Transitions from flat to HNSW index at a specified threshold ([read more](./indexing.mdx#dynamic-indexes)) |
| HFresh     | 🟨 Warm        | Sensitive to posting-list I/O | Memory-constrained deployments | A cluster-based index with memory efficiency for large datasets ([read more](./indexing.mdx#hfresh-indexes)) |

The choice depends on the representation you use, the latency you measure at the data volume you expect per collection or tenant, and the memory budget. The chart shows starting points for collections and tenants. The [index options](./indexing.mdx) list every choice and its limits.

```mermaid
flowchart LR
    %% Define nodes and connections
    subgraph vectorIndex ["Vector Index Selection"]
        direction LR
        multiVector{"Does the workload use<br> multi-vector embeddings?"}
        flatLatency{"Does a flat scan on the data<br> you expect per collection<br> or tenant meet your<br> measured latency target?"}
        hnswMemory{"Does the HNSW payload<br> and graph fit the<br> memory budget?"}
        growing{"Do collections or tenants<br> start small and grow, with<br> async indexing and an<br> experimental index<br> acceptable?"}

        multiVector -->|No| flatLatency
        multiVector -->|Yes| multiVectorNote["Check the supported<br> index and encoding<br> combinations"]
        flatLatency -->|Yes| useFlat["Start with flat"]
        flatLatency -->|No| hnswMemory
        hnswMemory -->|Yes| growing
        hnswMemory -->|No| useHfresh["Consider compression<br> or HFresh"]
        growing -->|Yes| useDynamic["Consider dynamic"]
        growing -->|No| useHNSW["Start with HNSW"]
    end

    %% Style nodes
    style multiVector fill:#ffffff,stroke:#B9C8DF,color:#130C49
    style flatLatency fill:#ffffff,stroke:#B9C8DF,color:#130C49
    style hnswMemory fill:#ffffff,stroke:#B9C8DF,color:#130C49
    style growing fill:#ffffff,stroke:#B9C8DF,color:#130C49

    %% Terminal nodes
    style useFlat fill:#ffffff,stroke:#61BD73,color:#130C49
    style useHNSW fill:#ffffff,stroke:#61BD73,color:#130C49
    style useDynamic fill:#ffffff,stroke:#61BD73,color:#130C49
    style useHfresh fill:#ffffff,stroke:#61BD73,color:#130C49
    style multiVectorNote fill:#ffffff,stroke:#D6A400,color:#130C49

    %% Style subgraph
    style vectorIndex fill:#ffffff,stroke:#130C49,stroke-width:2px,color:#130C49
```

The questions use your own measurements, not fixed object counts:

- **Multi-vector embeddings**: `flat` and `dynamic` do not support them, and HFresh requires MUVERA encoding. See [Multi-vector embeddings](../../configuration/compression/multi-vectors.md).
- **Flat latency**: a `flat` query scans the eligible vectors, so measure it with your dimensions, filters and the data volume you expect per collection or tenant.
- **HNSW memory**: size the payload, graph, shards and replicas. See [Resource planning](../../concepts/resources.md#choose-a-starting-configuration).
- **Growth**: the [dynamic index](../../concepts/indexing/vector-index.md#dynamic-index) requires async indexing, is experimental, converts from flat to HNSW only and does not support multi-vector embeddings. It defers the HNSW memory cost while a collection or tenant is small. Its HNSW stage is an HNSW index, so a partition that grows past the threshold needs the memory budget that the previous question asks about.
- **Memory-constrained**: compare a compressed HNSW index with HFresh, and measure recall, latency and disk use on your storage.

For details, see the [starter guide: indexes](./indexing.mdx) and [how-to: set the vector index type](../../manage-collections/vector-config.mdx#set-vector-index-type).

### Vector compression

Vector compression techniques reduce the size of vectors by quantizing them into a smaller representation.

This can have the impact of reducing memory usage, or improving performance by reducing the amount of data that needs to be read from disk. The trade-off is that the resulting search quality may be lower.

Weaviate supports the following vector compression methods:

| Compression Method        | Index Type | Requires Training | Description |
|---------------------------|------------|-------------------|-------------|
| Product Quantization (PQ) | HNSW       | Yes               | Each vector becomes an array of integer-based centroids ([read more](../../concepts/vector-quantization.md#product-quantization)) |
| Binary Quantization (BQ)  | HNSW, Flat | No                | Each vector dimension becomes a bit ([read more](../../concepts/vector-quantization.md#binary-quantization)) |
| Scalar Quantization (SQ)  | HNSW       | Yes               | Each vector dimension becomes an integer ([read more](../../concepts/vector-quantization.md#scalar-quantization)) |
| Rotational Quantization (RQ) | All index types | No, except 4-bit RQ with `centering` | Each vector is rotated then quantized to an integer ([read more](../../concepts/vector-quantization.md#rotational-quantization)) |

As a starting point, use the following guidelines for selecting a compression method:

```mermaid
flowchart LR
    %% Define nodes and connections
    subgraph compression ["Compression Strategy"]
        direction LR
        startIndexType{"What is your<br> vector index type?"}
        sample{"Do you have a<br> representative sample<br> of your final dataset?"}
        tunable{"Do you want<br> tunable<br> compression?"}
        bqcompat{"Is your vectorizer<br> model compatible<br> with BQ?"}

        startIndexType -->|HNSW| sample
        startIndexType -->|Flat| bqcompat
        sample -->|Yes| tunable
        tunable -->|Yes| usePQ["Use PQ"]
        tunable -->|No| useSQ["Use SQ"]
        sample -->|No| useBQ["Use BQ"]
        bqcompat -->|Yes| useBQ["Use BQ"]
        bqcompat -->|No| noCompress["Do not use<br> compression"]
    end

    %% Style nodes
    style startIndexType fill:#ffffff,stroke:#B9C8DF,color:#130C49
    style sample fill:#ffffff,stroke:#B9C8DF,color:#130C49
    style tunable fill:#ffffff,stroke:#B9C8DF,color:#130C49
    style bqcompat fill:#ffffff,stroke:#B9C8DF,color:#130C49

    %% Terminal nodes
    style usePQ fill:#ffffff,stroke:#61BD73,color:#130C49
    style useSQ fill:#ffffff,stroke:#61BD73,color:#130C49
    style useBQ fill:#ffffff,stroke:#61BD73,color:#130C49
    style noCompress fill:#ffffff,stroke:#61BD73,color:#130C49

    %% Style subgraph
    style compression fill:#ffffff,stroke:#7AD6EB,stroke-width:2px,color:#130C49
```

If you are unsure which index type to use, scalar quantization is a good starting point, provided that you have a representative sample of your likely final dataset.

- [Starter guide: Vector compression](./compression.mdx)
- [How-to: Configure vector compression](../../configuration/compression/index.md)

### Tenant states

Multi-tenant collections enable you to efficiently manage isolated subsets of data. Each tenant share the same schema and configuration.

Weaviate supports the following tenant states:

| Tenant state     | CRUD & Queries | Vector Index | Inverted Index | Object Data | Time to Activate |Description |
|------------------|----------------|--------------|----------------|-------------|------------------|------------|
| Active (default) | **Yes**        | Hot/Warm     | Warm           | Warm        | None             |Tenant is available for use |
| Inactive         | **No**         | Warm         | Warm           | Warm        | Fast             |Tenant is locally stored but not available for use |
| Offloaded        | **No**         | Cold         | Cold           | Cold        | Slow             |Tenant is stored in cloud storage and not available for use |

*Hot* tenants can be deactivated to *warm* storage to reduce memory usage, and any tenant can be offloaded to *cold* storage to reduce memory and disk usage. Conversely, any tenant can be reactivated when needed.

```mermaid
flowchart LR
    %% Define nodes and connections
    subgraph tenantData ["Tenant Data Availability"]
        direction LR
        needNow{"Does the tenant data<br> need to be<br> available now?"}
        howQuick{"When it is needed,<br> how quickly does it<br> need to be available?"}

        needNow -->|Yes| active["Active"]
        needNow -->|No| howQuick
        howQuick -->|Quickly| inactive["Inactive"]
        howQuick -->|"Latency is acceptable"| offloaded["Offloaded"]
    end

    %% Style nodes
    style needNow fill:#ffffff,stroke:#B9C8DF,color:#130C49
    style howQuick fill:#ffffff,stroke:#B9C8DF,color:#130C49

    %% Terminal nodes
    style active fill:#ffffff,stroke:#61BD73,color:#130C49
    style inactive fill:#ffffff,stroke:#61BD73,color:#130C49
    style offloaded fill:#ffffff,stroke:#61BD73,color:#130C49

    %% Style subgraph
    style tenantData fill:#ffffff,stroke:#61BD73,stroke-width:2px,color:#130C49
```

Consider a strategy of deactivating tenants that are not frequently accessed, and offloading tenants that are rarely accessed.

- [Starter guide: tenant states](./tenant-states.mdx)
- [How-to: Configure tenant offloading](/deploy/configuration/tenant-offloading.md)
- [How-to: Manage tenant states](../../manage-collections/tenant-states.mdx)

## Tips

### Best Practices

- Start with the dynamic [index type](#vector-index-types) for new collections. This is particularly useful for multi-tenant collections, as it allows each tenant to use the most appropriate index type.
- Use [vector compression](#vector-compression) techniques to optimize storage and query performance, especially for large collections or tenants.
- Conduct thorough testing when changing index types or compression methods to ensure performance meets your requirements.

### Common Pitfalls

- Overprovisioning hot storage: Keeping all data in hot storage can lead to unnecessary costs. Regularly assess what data truly needs the fastest access.
- Neglecting to plan for growth: Not anticipating data growth can lead to performance issues. Always design your resource management strategy with scalability in mind.
- Improper tenant management: In multi-tenant scenarios, forgetting to [offload inactive tenants](#tenant-states) can lead to resource waste. Implement automated processes to manage tenant states based on usage patterns.
- Mismatch between quantization techniques, model and data: When using compression technique, ensure that the quantization technique is compatible with the model (e.g. BQ) and that the data is sufficient and representative for training (e.g. PQ, SQ).

## Related pages

- [Starter guide: Compression](./compression.mdx)
- [Starter guide: Indexing](./indexing.mdx)
- [Starter guide: Tenant states](./tenant-states.mdx)
- [Concepts: Vector Index](../../concepts/indexing/vector-index.md)
- [Concepts: Vector Quantization](../../concepts/vector-quantization.md)
- [Concepts: Multi-Tenancy](../../concepts/data.md#multi-tenancy)
- [How-to: Set the vector index type](../../manage-collections/vector-config.mdx#set-vector-index-type)
- [How-to: Configure vector compression](../../configuration/compression/index.md)
- [How-to: Perform multi-tenancy operations](../../manage-collections/multi-tenancy.mdx)
- [How-to: Manage tenant states](../../manage-collections/tenant-states.mdx)

## Questions and feedback

import DocsFeedback from '/_includes/docs-feedback.mdx';

<DocsFeedback/>
