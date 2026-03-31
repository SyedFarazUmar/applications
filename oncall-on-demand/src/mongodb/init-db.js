db = db.getSiblingDB("oncall_db");

db.createCollection("users");
db.createCollection("oncall_entries");

db.users.createIndex({ username: 1 }, { unique: true });
db.oncall_entries.createIndex({ username: 1 });
db.oncall_entries.createIndex({ oncall_primary_date: 1 });
db.oncall_entries.createIndex({ oncall_secondary_date: 1 });

print("oncall_db initialized with collections and indexes");
