import weaviate
import weaviate.classes as wvc
import json
import os
import urllib.request

# START ConnectToWeaviate
# Connect to Weaviate instance
client = weaviate.connect_to_local(
    headers={
        "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"]  # Replace with your API key
    }
)
# END ConnectToWeaviate

# START LoadData
# Download dataset directly from URL
url = "https://raw.githubusercontent.com/weaviate-tutorials/quickstart/main/data/jeopardy_tiny.json"
urllib.request.urlretrieve(url, "jeopardy_tiny.json")

# Load data from JSON file
with open("jeopardy_tiny.json", "r") as f:
    data = json.load(f)

# Prepare data for import
data_rows = []
for item in data:
    data_rows.append(
        {
            "question": item["Question"],
            "answer": item["Answer"],
            "category": item["Category"],
        }
    )

print(f"Loaded {len(data_rows)} questions")
expected_count = len(data_rows)
# END LoadData

# Clean up any existing collection
client.collections.delete("JeopardyQuestion")

# START CreateCollection
# Create a collection for Jeopardy questions
collection = client.collections.create(
    name="JeopardyQuestion",
    vector_config=wvc.config.Configure.Vectors.text2vec_openai(),
    properties=[
        wvc.config.Property(name="question", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="answer", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="category", data_type=wvc.config.DataType.TEXT),
    ],
)
# END CreateCollection

# START ServerSideBatch
# Server-side batching (automatic mode)
# The server manages the import flow automatically
with collection.batch.stream() as batch:
    # Import data
    for data_row in data_rows:
        batch.add_object(
            properties=data_row,
        )

        # Optional: Stop if too many errors
        if batch.number_errors > 10:
            print("Batch import stopped due to excessive errors.")
            break

# Check for failed objects
failed_objects = collection.batch.failed_objects
if failed_objects:
    print(f"Number of failed imports: {len(failed_objects)}")
    print(f"First failed object: {failed_objects[0]}")
else:
    print("All objects imported successfully!")

# Verify server-side batch import
result = collection.aggregate.over_all(total_count=True)
assert len(failed_objects) == 0, f"Server-side batch had {len(failed_objects)} failures"
assert (
    result.total_count == expected_count
), f"Expected {expected_count} objects, got {result.total_count}"
print(f"✓ Server-side batch: {result.total_count} objects imported successfully")
# END ServerSideBatch

# Alternative approach - Client-side batching
# Clean and recreate collection for demo
client.collections.delete("JeopardyQuestion")
collection = client.collections.create(
    name="JeopardyQuestion",
    vector_config=wvc.config.Configure.Vectors.text2vec_openai(),
    properties=[
        wvc.config.Property(name="question", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="answer", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="category", data_type=wvc.config.DataType.TEXT),
    ],
)

# START ClientSideBatch
# Client-side batching with manual configuration
# You control batch size and concurrency
with collection.batch.fixed_size(
    batch_size=100,  # Number of objects per batch
    concurrent_requests=2,  # Number of parallel requests
) as batch:
    # Import data
    for data_row in data_rows:
        batch.add_object(
            properties=data_row,
        )

# Check for failed objects
failed_objects = collection.batch.failed_objects
if failed_objects:
    print(f"Number of failed imports: {len(failed_objects)}")
    for failed in failed_objects[:3]:  # Show first 3 failures
        print(f"Failed object: {failed}")

# Verify client-side batch import
result = collection.aggregate.over_all(total_count=True)
assert len(failed_objects) == 0, f"Client-side batch had {len(failed_objects)} failures"
assert (
    result.total_count == expected_count
), f"Expected {expected_count} objects, got {result.total_count}"
print(f"✓ Client-side batch: {result.total_count} objects imported successfully")
# END ClientSideBatch

# START ErrorHandling
# Comprehensive error handling during import
# Clean and recreate for demo
client.collections.delete("JeopardyQuestion")
collection = client.collections.create(
    name="JeopardyQuestion",
    vector_config=wvc.config.Configure.Vectors.text2vec_openai(),
    properties=[
        wvc.config.Property(name="question", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="answer", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="category", data_type=wvc.config.DataType.TEXT),
    ],
)

import_errors = []

with collection.batch.fixed_size(batch_size=100) as batch:
    for idx, data_row in enumerate(data_rows):
        try:
            batch.add_object(properties=data_row)
        except Exception as e:
            import_errors.append({"index": idx, "data": data_row, "error": str(e)})
            continue

        # Check batch errors periodically
        if idx % 100 == 0 and idx > 0:
            if batch.number_errors > 0:
                print(f"Errors at index {idx}: {batch.number_errors}")
                # Optionally retrieve and log failed objects
                for failed_obj in collection.batch.failed_objects[-10:]:
                    print(f"Failed: {failed_obj.message}")

# Final error report
if import_errors:
    print(f"\nTotal import errors: {len(import_errors)}")
    print("Sample errors:")
    for error in import_errors[:3]:
        print(f"  Index {error['index']}: {error['error']}")
# END ErrorHandling

# START VerifyImport
# Verify the import was successful
result = collection.aggregate.over_all(total_count=True)
print(f"\nTotal objects in collection: {result.total_count}")

# Query a few objects to verify
results = collection.query.fetch_objects(limit=3)
print("\nSample imported objects:")
for obj in results.objects:
    print(f"- Question: {obj.properties['question'][:50]}...")
    print(f"  Answer: {obj.properties['answer']}")
    print(f"  Category: {obj.properties['category']}\n")
# END VerifyImport

# START CustomVectors
# Import with custom vectors (if you have pre-computed embeddings)
import numpy as np

# Example: Create a collection that accepts custom vectors
client.collections.delete("JeopardyCustomVectors")
collection_custom = client.collections.create(
    name="JeopardyCustomVectors",
    vector_config=wvc.config.Configure.Vectors.self_provided(),
    properties=[
        wvc.config.Property(name="question", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="answer", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="category", data_type=wvc.config.DataType.TEXT),
    ],
)

# Import objects with custom vectors
custom_import_count = 5  # Import first 5 for demo
with collection_custom.batch.fixed_size(batch_size=100) as batch:
    for data_row in data_rows[:custom_import_count]:
        # Generate a random vector for demonstration
        # In practice, this would be your pre-computed embedding
        custom_vector = np.random.rand(1536).tolist()

        batch.add_object(
            properties={
                "question": data_row["question"],
                "answer": data_row["answer"],
                "category": data_row["category"],
            },
            vector=custom_vector,
        )

# Verify custom vectors import
failed_custom = collection_custom.batch.failed_objects
result_custom = collection_custom.aggregate.over_all(total_count=True)
assert (
    len(failed_custom) == 0
), f"Custom vectors batch had {len(failed_custom)} failures"
assert (
    result_custom.total_count == custom_import_count
), f"Expected {custom_import_count} objects, got {result_custom.total_count}"
print(f"✓ Custom vectors: {result_custom.total_count} objects imported successfully!")
# END CustomVectors


# START ChunkedImport
import json
import uuid
from pathlib import Path

CHECKPOINT_PATH = Path("import_checkpoint.json")
# Label for this source snapshot and its target collection. Do not change it to
# re-send a corrected row; change it only for a new import into a new collection.
DATASET_NAME = "jeopardy-tiny-v1"


def object_id(position):
    """Return the ID for the row at this position in the dataset.

    The ID must be stable across runs, so a replay updates the same object
    instead of adding a copy, and unique in the dataset, because a batch write
    with an existing ID overwrites that object. This example derives it from
    the dataset label and the row position. If the source has its own immutable
    key, use that instead. Do not derive it from a property that you may edit:
    edited text gives a new ID, and two equal texts give the same ID.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DATASET_NAME}/{position}"))


def load_checkpoint(dataset, collection_name):
    """Return the checkpoint for this dataset and collection, or a fresh one."""
    if not CHECKPOINT_PATH.exists():
        return {
            "dataset": dataset,
            "collection": collection_name,
            "next_start": 0,
            "acknowledged_in_chunk": [],
        }
    checkpoint = json.loads(CHECKPOINT_PATH.read_text())
    if checkpoint.get("dataset") != dataset or checkpoint.get("collection") != collection_name:
        raise ValueError(
            f"{CHECKPOINT_PATH} belongs to dataset {checkpoint.get('dataset')!r} in collection "
            f"{checkpoint.get('collection')!r}, not {dataset!r} in {collection_name!r}. "
            "Delete it or use a different path."
        )
    return checkpoint


def save_checkpoint(dataset, collection_name, next_start, acknowledged_ids):
    CHECKPOINT_PATH.write_text(
        json.dumps(
            {
                "dataset": dataset,
                "collection": collection_name,
                "next_start": next_start,
                "acknowledged_in_chunk": sorted(acknowledged_ids),
            }
        )
    )


def import_large_dataset(collection, data_rows, chunk_size=1000):
    """Import rows in chunks and stop at the first chunk that is not fully acknowledged.

    The checkpoint records the dataset label, the collection, the row position
    to resume from and the IDs already acknowledged at or after that position.
    A later call resumes at that row, does not re-send those IDs, and accepts a
    different `chunk_size`.

    The label is not a checksum. A safe resume depends on the ordered rows and
    their IDs staying the same, and on acknowledged payloads and the target
    collection not changing. You may correct the payload of a row that was not
    acknowledged: its ID stays the same, so the next call writes the corrected
    row.

    The checkpoint compares only the dataset label and the collection name. It
    cannot tell another cluster, another tenant, or a collection that was
    deleted and recreated under the same name. Use a separate checkpoint file
    and dataset label for each destination, and delete the checkpoint when you
    recreate the collection.

    `data_rows` must be an indexable sequence in a stable order, so that a row
    position identifies the same row on the next call.

    Returns:
        A dict whose `state` is `"complete"` or `"stopped"`. `acknowledged` is
        the number of objects acknowledged during this call. On `"stopped"`,
        `failed` and `unresolved` list the object IDs that failed or whose
        outcome is unknown; the checkpoint re-sends them on the next call.
    """
    if chunk_size < 1:
        raise ValueError(f"chunk_size must be at least 1, got {chunk_size}.")

    collection_name = collection.name
    checkpoint = load_checkpoint(DATASET_NAME, collection_name)
    if checkpoint["next_start"] > len(data_rows):
        raise ValueError(
            f"The checkpoint resumes at row {checkpoint['next_start']}, but there are only "
            f"{len(data_rows)} rows. Use the source snapshot that the checkpoint belongs to."
        )
    acknowledged = set(checkpoint["acknowledged_in_chunk"])
    confirmed = 0

    for chunk_start in range(checkpoint["next_start"], len(data_rows), chunk_size):
        chunk_end = min(chunk_start + chunk_size, len(data_rows))
        chunk_ids = {position: object_id(position) for position in range(chunk_start, chunk_end)}
        pending = [
            (position, chunk_ids[position])
            for position in range(chunk_start, chunk_end)
            if chunk_ids[position] not in acknowledged
        ]
        if not pending:  # Every row in this chunk is already acknowledged.
            acknowledged.difference_update(chunk_ids.values())
            save_checkpoint(DATASET_NAME, collection_name, chunk_end, acknowledged)
            continue

        with collection.batch.stream() as batch:
            for position, uid in pending:
                batch.add_object(properties=data_rows[position], uuid=uid)

        # The batch context has closed, so this chunk's results are complete.
        sent = {uid for _, uid in pending}
        acked = {str(uid) for uid in collection.batch.results.objs.uuids.values()}
        failed = {str(error.object_.uuid) for error in collection.batch.failed_objects}
        unresolved = sent - acked - failed
        acknowledged |= acked
        confirmed += len(acked)

        print(
            f"Chunk rows {chunk_start}-{chunk_end - 1}: {len(acked)} acknowledged, "
            f"{len(failed)} failed, {len(unresolved)} unresolved"
        )

        if failed or unresolved:
            # Keep every acknowledged ID from the resume row onwards: a later
            # chunk may already have confirmed rows past this one.
            save_checkpoint(DATASET_NAME, collection_name, chunk_start, acknowledged)
            return {
                "state": "stopped",
                "acknowledged": confirmed,
                "failed": sorted(failed),
                "unresolved": sorted(unresolved),
            }

        acknowledged.difference_update(chunk_ids.values())
        save_checkpoint(DATASET_NAME, collection_name, chunk_end, acknowledged)

    print(f"Import complete: {len(data_rows)} rows are covered by acknowledged writes.")
    return {"state": "complete", "acknowledged": confirmed, "failed": [], "unresolved": []}
# END ChunkedImport

# Demo: create a fresh collection, then run the import twice. This setup and
# reset belong to the script, not to the resumable recipe above.
CHECKPOINT_PATH.unlink(missing_ok=True)
client.collections.delete("JeopardyQuestion")
collection = client.collections.create(
    name="JeopardyQuestion",
    vector_config=wvc.config.Configure.Vectors.text2vec_openai(),
    properties=[
        wvc.config.Property(name="question", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="answer", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="category", data_type=wvc.config.DataType.TEXT),
    ],
)

first = import_large_dataset(collection, data_rows, chunk_size=3)
assert first["state"] == "complete", first
# A second call resumes from the checkpoint and covers the rows it has not
# acknowledged yet, also with a different chunk size.
second = import_large_dataset(collection, data_rows, chunk_size=4)
assert second["state"] == "complete", second

result_chunked = collection.aggregate.over_all(total_count=True)
assert (
    result_chunked.total_count == expected_count
), f"Expected {expected_count} objects, got {result_chunked.total_count}"
print(f"✓ Chunked import: {result_chunked.total_count} objects imported successfully")

# Clean up
client.collections.delete("JeopardyQuestion")
client.collections.delete("JeopardyCustomVectors")
os.remove("import_checkpoint.json")
os.remove("jeopardy_tiny.json")
client.close()
