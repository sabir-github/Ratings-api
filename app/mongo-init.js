db = db.getSiblingDB('company_db');

// Create companies collection with validation
db.createCollection('companies', {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["id", "company_code", "company_name", "active", "created_at", "updated_at"],
      properties: {
        id: {
          bsonType: "long",
          description: "must be a long and is required"
    },
    company_code: {
      bsonType: "string",
      description: "must be a string and is required"
    },
    company_name: {
      bsonType: "string",
      description: "must be a string and is required"
    },
    active: {
      bsonType: "bool",
      description: "must be a boolean and is required"
    },
    created_at: {
      bsonType: "date",
      description: "must be a date and is required"
    },
    updated_at: {
      bsonType: "date",
      description: "must be a date and is required"
    }
  }
}
});

// Create indexes
db.companies.createIndex({ "id": 1 }, { unique: true });
db.companies.createIndex({ "company_code": 1 }, { unique: true });
db.companies.createIndex({ "company_name": 1 });
db.companies.createIndex({ "active": 1 });