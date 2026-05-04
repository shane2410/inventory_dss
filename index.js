const express = require("express");
const { MongoClient } = require("mongodb");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());

const uri = process.env.MONGODB_URI;
const client = new MongoClient(uri);

let db;

async function connectDB() {
  await client.connect();
  db = client.db("inventory"); // bạn đặt tên DB tùy ý
  console.log("MongoDB connected");
}

connectDB();

app.get("/api/items", async (req, res) => {
  const data = await db.collection("items").find().toArray();
  res.json(data);
});

app.post("/api/items", async (req, res) => {
  const result = await db.collection("items").insertOne(req.body);
  res.json(result);
});

app.get("/", (req, res) => {
  res.send("API running...");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("Server running"));
