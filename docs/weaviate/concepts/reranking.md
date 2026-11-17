---
title: Reranking
sidebar_position: 28
description: "Search result reordering techniques using alternative models to improve search relevance and accuracy."
image: og/docs/concepts.jpg
# tags: ['basics']
---

Reranking seeks to improve search relevance by reordering the result set returned by a search with a different model.

Reranking computes a relevance score between the query and each data object, and returns the list of objects sorted from the most to the least relevant. Computing this score for all `(query, data_object)` pairs would typically be prohibitively slow, which is why reranking is used as a second stage after retrieving the relevant objects first.

As the reranker works on a smaller subset of data after retrieval, different, potentially more computationally expensive approaches can be used to improve search relevance.

:::info

Learn how to [set up a reranker for your collection](../manage-collections/generative-reranker-models.mdx#specify-a-reranker-model-integration) and [apply reranking to your search results](../search/rerank.md).

:::

## Reranking in Weaviate

With our reranker modules, you can conveniently perform [multi-stage searches](https://weaviate.io/blog/cross-encoders-as-reranker) without leaving Weaviate.

In other words, you can perform a search - for example, a vector search - and then use a reranker to re-rank the results of that search. Our reranker modules are compatible with all of vector, bm25, and hybrid searches.

### Choose the candidate set

A reranker can change the order of the retrieved objects, but it cannot recover an object that retrieval missed or a filter excluded. If relevant objects are missing, adjust the retrieval query, filters or `limit` before changing the reranker.

Without other result-selection options, your application can retrieve more than 10 candidates, rerank them, and keep the first 10. Options such as `autocut` and [MMR](../search/similarity.md#diversity-selection-mmr) can reduce the set before reranking, so increasing `limit` alone does not guarantee more candidates. More candidates can increase reranking work and provider costs. Compare relevance, latency and cost on your workload.

### An example GraphQL query with a reranker

You can use reranking in a GraphQL query as follows:

```graphql
{
  Get {
    JeopardyQuestion(
      nearText: {
        concepts: "flying"
      }
      limit: 10
    ) {
      answer
      question
      _additional {
        distance
        rerank(
          property: "answer"
          query: "floating"
        ) {
          score
        }
      }
    }
  }
}
```

This query retrieves up to 10 results from the `JeopardyQuestion` class, using a vector search (`nearText`) with the query "flying". It then re-ranks the results using the `answer` property and the query "floating".

The required `property` parameter selects the text to pass to the reranker. In GraphQL, request `rerank { score }` under `_additional` for the reranker's score. Reranking itself leaves `_additional.score` and `_additional.distance` unchanged.

## Further resources

:::info Related pages
- [API References: GraphQL - Additional properties](../api/graphql/additional-properties.md#rerank)
- [How-to search: Rerank](../search/rerank.md)
- [Cohere reranker integration](../model-providers/cohere/reranker.md)
- [Transformers reranker integration](../model-providers/transformers/reranker.md)
- [VoyageAI reranker integration](../model-providers/voyageai/reranker.md)
:::

## Questions and feedback

import DocsFeedback from '/_includes/docs-feedback.mdx';

<DocsFeedback/>
