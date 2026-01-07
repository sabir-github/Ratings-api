// mongo-init.js

db.createUser({
  user: "admin",
  pwd: "password",
  roles: [
    { role: "readWrite", db: "ratings_db" }
  ]
});