"""
MongoDB connection and operations for inventory system
"""
import os
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import logging

logger = logging.getLogger(__name__)

# Get MongoDB URI from environment or use local.
# Prefer the deployment variable name already used in render.yaml.
MONGODB_URI = os.environ.get('MONGO_URI') or os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017'
DB_NAME = 'inventory_dss'

class MongoDBConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBConnection, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[DB_NAME]
            logger.info(f"✅ Connected to MongoDB: {DB_NAME}")
            self._initialized = True
        except ServerSelectionTimeoutError:
            logger.error("❌ Cannot connect to MongoDB")
            self.client = None
            self.db = None
            self._initialized = True
    
    def get_db(self):
        return self.db
    
    def is_connected(self):
        return self.db is not None


# Get MongoDB connection
def get_mongo_db():
    """Get MongoDB database instance"""
    connection = MongoDBConnection()
    return connection.get_db()


# ============================================
# MATERIAL OPERATIONS
# ============================================
def insert_material(name, on_hand=0, holding_cost=0, ordering_cost=0, price_cost=0, source_id=None):
    """Insert new material to MongoDB"""
    db = get_mongo_db()
    if db is None:
        return None
    
    material = {
        'name': name,
        'on_hand': on_hand,
        'holding_cost': holding_cost,
        'ordering_cost': ordering_cost,
        'price_cost': price_cost,
        'source_id': source_id,
    }
    result = db.materials.insert_one(material)
    logger.info(f"✅ Inserted material: {result.inserted_id}")
    return result.inserted_id


def get_all_materials():
    """Get all materials from MongoDB"""
    db = get_mongo_db()
    if db is None:
        return []
    
    materials = list(db.materials.find())
    return materials


def get_material_by_id(material_id):
    """Get material by MongoDB ObjectId"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    material = db.materials.find_one({'_id': ObjectId(material_id)})
    return material


def get_material_by_name(name):
    """Get material by name"""
    db = get_mongo_db()
    if db is None:
        return None
    
    material = db.materials.find_one({'name': name})
    return material


def update_material(material_id, **kwargs):
    """Update material in MongoDB"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    result = db.materials.update_one(
        {'_id': ObjectId(material_id)},
        {'$set': kwargs}
    )
    logger.info(f"✅ Updated material: {material_id}, Modified: {result.modified_count}")
    return result.modified_count


def delete_material(material_id):
    """Delete material from MongoDB"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    result = db.materials.delete_one({'_id': ObjectId(material_id)})
    logger.info(f"✅ Deleted material: {material_id}, Deleted: {result.deleted_count}")
    return result.deleted_count


# ============================================
# PRODUCT OPERATIONS
# ============================================
def insert_product(name, source_id=None):
    """Insert new product to MongoDB"""
    db = get_mongo_db()
    if db is None:
        return None
    
    product = {
        'name': name,
        'source_id': source_id,
    }
    result = db.products.insert_one(product)
    logger.info(f"✅ Inserted product: {result.inserted_id}")
    return result.inserted_id


def get_all_products():
    """Get all products from MongoDB"""
    db = get_mongo_db()
    if db is None:
        return []
    
    products = list(db.products.find())
    return products


def get_product_by_id(product_id):
    """Get product by MongoDB ObjectId"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    product = db.products.find_one({'_id': ObjectId(product_id)})
    return product


def update_product(product_id, **kwargs):
    """Update product in MongoDB"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    result = db.products.update_one(
        {'_id': ObjectId(product_id)},
        {'$set': kwargs}
    )
    logger.info(f"✅ Updated product: {product_id}, Modified: {result.modified_count}")
    return result.modified_count


def delete_product(product_id):
    """Delete product from MongoDB"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    result = db.products.delete_one({'_id': ObjectId(product_id)})
    logger.info(f"✅ Deleted product: {product_id}, Deleted: {result.deleted_count}")
    return result.deleted_count


# ============================================
# TRANSACTION OPERATIONS
# ============================================
def insert_transaction(material_id, transaction_type, quantity, notes=""):
    """Insert new transaction to MongoDB"""
    from datetime import datetime
    db = get_mongo_db()
    if db is None:
        return None
    
    transaction = {
        'material_id': material_id,
        'type': transaction_type,  # 'IN', 'OUT'
        'quantity': quantity,
        'notes': notes,
        'date': datetime.now(),
    }
    result = db.transactions.insert_one(transaction)
    logger.info(f"✅ Inserted transaction: {result.inserted_id}")
    return result.inserted_id


def get_transactions_by_material(material_id):
    """Get all transactions for a material"""
    db = get_mongo_db()
    if db is None:
        return []
    
    transactions = list(db.transactions.find({'material_id': material_id}))
    return transactions


def update_transaction(transaction_id, **kwargs):
    """Update transaction in MongoDB"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    result = db.transactions.update_one(
        {'_id': ObjectId(transaction_id)},
        {'$set': kwargs}
    )
    logger.info(f"✅ Updated transaction: {transaction_id}, Modified: {result.modified_count}")
    return result.modified_count


def delete_transaction(transaction_id):
    """Delete transaction from MongoDB"""
    from bson.objectid import ObjectId
    db = get_mongo_db()
    if db is None:
        return None
    
    result = db.transactions.delete_one({'_id': ObjectId(transaction_id)})
    logger.info(f"✅ Deleted transaction: {transaction_id}, Deleted: {result.deleted_count}")
    return result.deleted_count
