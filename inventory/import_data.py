import os
import django
import pandas as pd

# ===== 🔥 FIX QUAN TRỌNG: SETUP DJANGO =====
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
django.setup()

from django.conf import settings
from inventory.models import Product, Material, BOM, SalesData, Transaction


def import_excel(file_path=None):

    # =========================
    # 0. FILE PATH
    # =========================
    if not file_path:
        default_new_file = os.path.join(settings.BASE_DIR, "data", "data_new.xlsx")
        legacy_file = os.path.join(settings.BASE_DIR, "data", "data_new_3.xlsx")

        # Prefer the new dataset file, but keep backward compatibility.
        file_path = default_new_file if os.path.exists(default_new_file) else legacy_file

    print("📂 USING FILE:", file_path)

    # =========================
    # 1. RESET DATA
    # =========================
    Transaction.objects.all().delete()
    SalesData.objects.all().delete()
    BOM.objects.all().delete()
    Material.objects.all().delete()
    Product.objects.all().delete()

    print("🗑️ Cleared old data")

    # =========================
    # HELPER: CLEAN COLUMNS
    # =========================
    def clean_df(df):
        df.columns = df.columns.str.strip()
        return df

    # =========================
    # 2. PRODUCT
    # =========================
    df_product = clean_df(pd.read_excel(file_path, sheet_name='Finished_Goods'))

    product_map = {}

    for _, row in df_product.iterrows():
        product_id = str(row.get('ProductID')).strip()
        name = str(row.get('ProductName', '')).strip()

        if not product_id or product_id == 'nan':
            continue

        product = Product.objects.create(source_id=product_id, name=name)
        product_map[product_id] = product

    print("✅ Imported Products:", len(product_map))

    # =========================
    # 3. MATERIAL
    # =========================
    df_material = clean_df(pd.read_excel(file_path, sheet_name='Raw_Materials'))

    material_map = {}

    for _, row in df_material.iterrows():
        material_id = str(row.get('MaterialID')).strip()
        name = str(row.get('MaterialName', '')).strip()

        if not material_id or material_id == 'nan':
            continue

        material = Material.objects.create(
            source_id=material_id,
            name=name,
            on_hand=row.get('QuantityOnHand', 0) or 0,
            on_order=row.get('On_order', 0) or 0,
            leadtime=row.get('Leadtime', 1) or 1,
            holding_cost=row.get('Holding_cost', 0) or 0,
            ordering_cost=row.get('Ordering_cost', 0) or 0,
            price_cost=row.get('UnitCost', 0) or 0,
        )

        material_map[material_id] = material

    print("✅ Imported Materials:", len(material_map))

    # =========================
    # 4. BOM
    # =========================
    df_bom = clean_df(pd.read_excel(file_path, sheet_name='BOM'))

    count_bom = 0

    for _, row in df_bom.iterrows():
        product = product_map.get(str(row.get('ProductID')).strip())
        material = material_map.get(str(row.get('MaterialID')).strip())

        if product and material:
            BOM.objects.create(
                product=product,
                material=material,
                quantity_per_unit=row.get('QuantityRequired', 0) or 0
            )
            count_bom += 1

    print("✅ Imported BOM:", count_bom)

    # =========================
    # 5. SALES
    # =========================
    df_sales = clean_df(pd.read_excel(file_path, sheet_name='Sales'))

    count_sales = 0

    for _, row in df_sales.iterrows():
        product = product_map.get(str(row.get('Product_id')).strip())

        if product:
            SalesData.objects.create(
                product=product,
                date=row.get('Date'),
                quantity=row.get('Sales_quantity', 0) or 0
            )
            count_sales += 1

    print("✅ Imported Sales:", count_sales)

    # =========================
    # 6. TRANSACTION
    # =========================
    df_trans = clean_df(pd.read_excel(file_path, sheet_name='Inventory_Transactions'))

    print("COLUMNS:", df_trans.columns)  # 👈 debug 1 lần

    count_trans = 0

    for _, row in df_trans.iterrows():
        material_id = str(row.get('MaterialID')).strip()
        material = material_map.get(material_id)

        if not material:
            print("❌ Missing Material:", material_id)
            continue

        # ===== FIX DATE =====
        date_value = row.get('Date')

        if pd.isna(date_value):
            print("❌ Missing Date → skip")
            continue

        # convert về datetime chuẩn
        date_value = pd.to_datetime(date_value)

        Transaction.objects.create(
            material=material,
            quantity=row.get('Quantity', 0) or 0,
            transaction_type=str(row.get('Type (IN/OUT)')).strip().upper(),
            date=date_value
        )

        count_trans += 1

    print("✅ Imported Transactions:", count_trans)

    print("🎉 DONE IMPORT ALL DATA")
# ===== CHẠY TRỰC TIẾP =====
if __name__ == "__main__":
    import_excel()
