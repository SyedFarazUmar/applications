# MongoDB Service — Code Reference Guide

The MongoDB service uses the official `mongo:7` Docker image with a custom initialization script (`init-db.js`) that creates the database, collections, and indexes on first startup. This document explains every construct used.

---

## Table of Contents

- [init-db.js (Initialization Script)](#init-dbjs-initialization-script)
  - [db.getSiblingDB()](#dbgetsiblingdb)
  - [db.createCollection()](#dbcreatecollection)
  - [db.collection.createIndex()](#dbcollectioncreateindex)
  - [print()](#print)
  - [JavaScript Object Syntax](#javascript-object-syntax)
- [How the Init Script Runs](#how-the-init-script-runs)
- [Dockerfile](#dockerfile)
- [MongoDB Concepts](#mongodb-concepts)
  - [Database](#database)
  - [Collection](#collection)
  - [Document](#document)
  - [Index](#index)
  - [Unique Index](#unique-index)
- [Data Schema](#data-schema)
  - [users Collection](#users-collection)
  - [oncall_entries Collection](#oncall_entries-collection)
- [Common mongosh Commands](#common-mongosh-commands)
  - [Connecting](#connecting)
  - [Querying Data](#querying-data)
  - [Inserting Data](#inserting-data)
  - [Updating Data](#updating-data)
  - [Deleting Data](#deleting-data)
  - [Index Management](#index-management)
  - [Database Administration](#database-administration)
- [How Python (PyMongo) Maps to mongosh](#how-python-pymongo-maps-to-mongosh)

---

## init-db.js (Initialization Script)

Here is the complete initialization script with explanations:

```javascript
db = db.getSiblingDB("oncall_db");

db.createCollection("users");
db.createCollection("oncall_entries");

db.users.createIndex({ username: 1 }, { unique: true });
db.oncall_entries.createIndex({ username: 1 });
db.oncall_entries.createIndex({ oncall_primary_date: 1 });
db.oncall_entries.createIndex({ oncall_secondary_date: 1 });

print("oncall_db initialized with collections and indexes");
```

---

### db.getSiblingDB()

```javascript
db = db.getSiblingDB("oncall_db");
```

- `db` is a global variable in the MongoDB shell that refers to the current database.
- `getSiblingDB("oncall_db")` switches to the `oncall_db` database (creates it if it doesn't exist).
- Equivalent to running `use oncall_db` in an interactive mongosh session.
- After this line, all subsequent `db.xxx` calls operate on `oncall_db`.

---

### db.createCollection()

```javascript
db.createCollection("users");
db.createCollection("oncall_entries");
```

- Creates a new collection (similar to a table in SQL databases).
- `"users"` and `"oncall_entries"` are the collection names.
- MongoDB creates collections automatically when you first insert data, but `createCollection()` creates them explicitly so we can add indexes right away.
- If the collection already exists, this is a no-op (no error).

---

### db.collection.createIndex()

```javascript
db.users.createIndex({ username: 1 }, { unique: true });
db.oncall_entries.createIndex({ username: 1 });
db.oncall_entries.createIndex({ oncall_primary_date: 1 });
db.oncall_entries.createIndex({ oncall_secondary_date: 1 });
```

| Expression | Meaning |
|------------|---------|
| `db.users` | Access the `users` collection |
| `.createIndex(keys, options)` | Create an index on the specified fields |
| `{ username: 1 }` | Index on the `username` field; `1` = ascending order |
| `{ unique: true }` | Enforce uniqueness — no two documents can have the same `username` |

**Why indexes matter:**
- Without an index, MongoDB scans every document (slow on large collections).
- An index creates a sorted lookup structure — like a book's index — for fast queries.
- The `unique: true` option also acts as a constraint: inserting a duplicate `username` will fail with a `DuplicateKeyError`.

**Index direction (`1` vs `-1`):**

| Value | Meaning | Use case |
|-------|---------|----------|
| `1` | Ascending (A→Z, old→new) | Most queries |
| `-1` | Descending (Z→A, new→old) | Queries sorted in reverse |

For single-field indexes, the direction rarely matters. It becomes important for compound indexes.

---

### print()

```javascript
print("oncall_db initialized with collections and indexes");
```

- Outputs a message to the MongoDB shell's stdout.
- In Docker, this appears in the container logs during startup.
- Useful for confirming the init script ran successfully.

---

### JavaScript Object Syntax

```javascript
{ username: 1 }
{ unique: true }
{ username: 1, oncall_primary_date: 1 }
```

- MongoDB's shell uses JavaScript. Objects are written as `{ key: value }`.
- Keys don't need quotes when they are simple identifiers (no spaces, no special characters).
- `{ username: 1 }` is equivalent to `{ "username": 1 }`.
- This is the same syntax as JSON but with optional quotes on keys.

---

## How the Init Script Runs

```
Container starts
      │
      ▼
  Is /data/db empty?  ──No──▶  Skip initialization (data already exists)
      │
     Yes
      │
      ▼
  Run all scripts in /docker-entrypoint-initdb.d/
      │
      ▼
  Executes init-db.js
      │
      ▼
  MongoDB ready and accepting connections
```

- The official `mongo` Docker image looks for scripts in `/docker-entrypoint-initdb.d/` on first startup.
- Scripts ending in `.js` are executed against the `test` database by default (that's why we use `getSiblingDB()` to switch).
- Scripts ending in `.sh` are run as shell scripts.
- The scripts only run when the data directory is empty (first time). On subsequent restarts, they are skipped.

---

## Dockerfile

```dockerfile
FROM mongo:7
COPY init-db.js /docker-entrypoint-initdb.d/init-db.js
EXPOSE 27017
```

| Instruction | Purpose |
|-------------|---------|
| `FROM mongo:7` | Base image — official MongoDB 7.x image (includes mongosh, mongod, and all tools) |
| `COPY init-db.js /docker-entrypoint-initdb.d/init-db.js` | Place the init script where MongoDB's entrypoint will find and execute it |
| `EXPOSE 27017` | Documents that MongoDB listens on port 27017 (the default MongoDB port) |

This is a minimal Dockerfile — all MongoDB functionality comes from the base image. We only add our initialization script.

---

## MongoDB Concepts

### Database

A database is a container for collections. One MongoDB server can host many databases.

```javascript
use oncall_db          // Switch to a database (creates it if needed)
show dbs               // List all databases with data
db                     // Show current database name
```

In this app, the database is `oncall_db`.

---

### Collection

A collection is a group of documents (like a table in SQL). Collections live inside a database.

```javascript
show collections                    // List all collections in current database
db.createCollection("users")       // Create a collection explicitly
db.users.drop()                     // Delete a collection and all its data
```

This app has two collections: `users` and `oncall_entries`.

---

### Document

A document is a single record stored as BSON (Binary JSON). Documents are similar to JSON objects.

```javascript
{
    "_id": ObjectId("65f1a2b3c4d5e6f7a8b9c0d1"),
    "username": "admin",
    "password": "scrypt:32768:8:1$salt$hash...",
    "employee_id": "ADMIN-001",
    "created_at": ISODate("2026-03-31T12:00:00Z")
}
```

| Field | Description |
|-------|-------------|
| `_id` | Auto-generated unique identifier (ObjectId). Every document gets one |
| Other fields | Application-defined fields — MongoDB is schema-less, so documents in the same collection can have different fields |

---

### Index

An index is a data structure that makes queries faster. Without an index, MongoDB must scan every document (collection scan).

```
Without index:  Scan all 10,000 documents → Find matches → Slow
With index:     Jump directly to matching documents via B-tree → Fast
```

```javascript
db.oncall_entries.createIndex({ username: 1 })
```

This creates a B-tree index on the `username` field. Queries like `db.oncall_entries.find({ username: "admin" })` will use the index instead of scanning the entire collection.

---

### Unique Index

```javascript
db.users.createIndex({ username: 1 }, { unique: true })
```

A unique index adds a constraint: no two documents can have the same value for the indexed field. If you try to insert a duplicate:

```javascript
db.users.insertOne({ username: "admin", ... })  // OK (first time)
db.users.insertOne({ username: "admin", ... })  // ERROR: DuplicateKeyError
```

This is how the app enforces that usernames are unique.

---

## Data Schema

### users Collection

Stores registered user accounts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Auto | MongoDB's auto-generated unique identifier |
| `username` | String | Yes | Unique login name (indexed, unique constraint) |
| `password` | String | Yes | Hashed password (never stored in plain text) |
| `employee_id` | String | Yes | Employee identifier (e.g., `ADMIN-001`) |
| `created_at` | Date | Yes | Account creation timestamp |

**Example document:**
```json
{
    "_id": "ObjectId(...)",
    "username": "admin",
    "password": "scrypt:32768:8:1$aBcDeFgH$1234567890abcdef...",
    "employee_id": "ADMIN-001",
    "created_at": "2026-03-31T12:00:00.000Z"
}
```

---

### oncall_entries Collection

Stores on-call schedule entries submitted via the dashboard.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Auto | MongoDB's auto-generated unique identifier |
| `username` | String | Yes | Who this entry belongs to (indexed) |
| `employee_id` | String | Yes | Employee identifier |
| `oncall_primary_date` | String | Yes | Primary on-call date in `YYYY-MM-DD` format (indexed) |
| `oncall_secondary_date` | String | Yes | Secondary on-call date in `YYYY-MM-DD` format (indexed) |
| `created_at` | Date | Yes | Entry creation timestamp |

**Example document:**
```json
{
    "_id": "ObjectId(...)",
    "username": "admin",
    "employee_id": "ADMIN-001",
    "oncall_primary_date": "2026-04-07",
    "oncall_secondary_date": "2026-04-14",
    "created_at": "2026-03-31T14:30:00.000Z"
}
```

---

## Common mongosh Commands

### Connecting

```bash
# Docker Compose
docker exec -it oncall-on-demand-mongodb-1 mongosh oncall_db

# Kubernetes
kubectl exec -it <mongodb-pod> -n oncall -- mongosh oncall_db

# Direct connection (if port is exposed)
mongosh "mongodb://localhost:27017/oncall_db"
```

---

### Querying Data

```javascript
// Find all documents in a collection
db.users.find()

// Pretty-print results
db.users.find().pretty()

// Find a specific document
db.users.find({ username: "admin" })

// Find one document (returns first match)
db.users.findOne({ username: "admin" })

// Find with projection (select specific fields)
db.oncall_entries.find({ username: "admin" }, { oncall_primary_date: 1, _id: 0 })
// Output: { "oncall_primary_date": "2026-04-07" }

// Count documents
db.oncall_entries.countDocuments({ username: "admin" })

// Sort results (1 = ascending, -1 = descending)
db.oncall_entries.find().sort({ created_at: -1 })

// Limit results
db.oncall_entries.find().limit(5)

// Combine sort and limit (most recent 5 entries)
db.oncall_entries.find({ username: "admin" }).sort({ created_at: -1 }).limit(5)
```

**Query operators:**
```javascript
// Greater than
db.oncall_entries.find({ oncall_primary_date: { $gt: "2026-06-01" } })

// In a list
db.users.find({ username: { $in: ["admin", "jdoe"] } })

// Regex match
db.users.find({ username: { $regex: "^adm" } })

// Exists check
db.users.find({ employee_id: { $exists: true } })
```

---

### Inserting Data

```javascript
// Insert one document
db.users.insertOne({
    username: "jdoe",
    password: "hashed-password-here",
    employee_id: "EMP-042",
    created_at: new Date()
})

// Insert multiple documents
db.oncall_entries.insertMany([
    { username: "admin", employee_id: "ADMIN-001", oncall_primary_date: "2026-04-07", oncall_secondary_date: "2026-04-14", created_at: new Date() },
    { username: "admin", employee_id: "ADMIN-001", oncall_primary_date: "2026-06-15", oncall_secondary_date: "2026-06-22", created_at: new Date() }
])
```

---

### Updating Data

```javascript
// Update one document
db.users.updateOne(
    { username: "admin" },                      // Filter: which document to update
    { $set: { employee_id: "ADMIN-002" } }     // Update: what to change
)

// Upsert: update if exists, insert if not
db.users.updateOne(
    { username: "admin" },
    { $setOnInsert: { password: "hash", employee_id: "ADMIN-001", created_at: new Date() } },
    { upsert: true }
)

// Update multiple documents
db.oncall_entries.updateMany(
    { username: "oldname" },
    { $set: { username: "newname" } }
)
```

**Update operators:**

| Operator | Purpose | Example |
|----------|---------|---------|
| `$set` | Set a field's value | `{ $set: { employee_id: "NEW" } }` |
| `$setOnInsert` | Set only when inserting (not updating) | Used in upsert operations |
| `$unset` | Remove a field | `{ $unset: { old_field: "" } }` |
| `$inc` | Increment a number | `{ $inc: { login_count: 1 } }` |
| `$push` | Add to an array | `{ $push: { tags: "oncall" } }` |

---

### Deleting Data

```javascript
// Delete one document
db.users.deleteOne({ username: "testuser" })

// Delete multiple documents
db.oncall_entries.deleteMany({ username: "testuser" })

// Delete all documents in a collection (keep the collection and indexes)
db.oncall_entries.deleteMany({})

// Drop the entire collection (removes collection, data, and indexes)
db.oncall_entries.drop()
```

---

### Index Management

```javascript
// List all indexes on a collection
db.users.getIndexes()
// Output:
// [
//   { "v": 2, "key": { "_id": 1 }, "name": "_id_" },
//   { "v": 2, "key": { "username": 1 }, "name": "username_1", "unique": true }
// ]

// Create an index
db.oncall_entries.createIndex({ username: 1 })

// Create a unique index
db.users.createIndex({ email: 1 }, { unique: true })

// Create a compound index (multiple fields)
db.oncall_entries.createIndex({ username: 1, oncall_primary_date: -1 })

// Drop an index by name
db.users.dropIndex("username_1")

// Drop all indexes except _id
db.users.dropIndexes()
```

---

### Database Administration

```javascript
// Show current database
db

// List all databases
show dbs

// Switch database
use oncall_db

// List collections
show collections

// Database stats
db.stats()

// Collection stats
db.users.stats()

// Server status
db.serverStatus()

// Check if MongoDB is alive (used by health checks)
db.adminCommand({ ping: 1 })

// Drop the entire database (DESTRUCTIVE — deletes everything)
db.dropDatabase()
```

---

## How Python (PyMongo) Maps to mongosh

The frontend and calculator services use PyMongo to interact with MongoDB. Here's how PyMongo calls map to mongosh commands:

| Operation | mongosh | PyMongo (Python) |
|-----------|---------|-----------------|
| Connect | `mongosh "mongodb://host:27017"` | `client = MongoClient("mongodb://host:27017")` |
| Select database | `use oncall_db` | `db = client["oncall_db"]` |
| Select collection | `db.users` | `users_col = db["users"]` |
| Find one | `db.users.findOne({ username: "admin" })` | `users_col.find_one({"username": "admin"})` |
| Find many | `db.users.find({ username: "admin" })` | `list(users_col.find({"username": "admin"}))` |
| Find with projection | `db.users.find({}, { _id: 0 })` | `users_col.find({}, {"_id": 0})` |
| Insert one | `db.users.insertOne({...})` | `users_col.insert_one({...})` |
| Update one | `db.users.updateOne(filter, update)` | `users_col.update_one(filter, update)` |
| Upsert | `db.users.updateOne(f, u, { upsert: true })` | `users_col.update_one(f, u, upsert=True)` |
| Count | `db.users.countDocuments({})` | `users_col.count_documents({})` |
| Sort | `db.entries.find().sort({ created_at: -1 })` | `oncall_col.find().sort("created_at", -1)` |
| Ping | `db.adminCommand({ ping: 1 })` | `client.admin.command("ping")` |

**Key differences:**
- mongosh uses **camelCase**: `findOne`, `insertOne`, `createIndex`
- PyMongo uses **snake_case**: `find_one`, `insert_one`, `create_index`
- mongosh `find()` returns results directly; PyMongo returns a **cursor** that needs `list()` to materialize
- PyMongo uses Python booleans (`True`/`False`) instead of JavaScript (`true`/`false`)
