import os
import django
from datetime import date, timedelta

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_project.settings')
django.setup()

from products.models import Product, Category
from pharmacies.models import Pharmacy
from django.contrib.auth import get_user_model

User = get_user_model()

# Create categories
categories_data = [
    {"name": "Disposables", "description": "Single-use surgical and medical items"},
    {"name": "Diagnostics", "description": "Equipment for measuring and monitoring"},
    {"name": "Protection", "description": "Personal protective equipment (PPE)"},
    {"name": "Instruments", "description": "Surgical and medical instruments"},
    {"name": "Sanitization", "description": "Cleaning and sanitizing supplies"},
    {"name": "Sutures", "description": "Surgical threads and needles"},
    {"name": "Wound Care", "description": "Dressings, bandages, and tapes"},
    {"name": "Orthopedics", "description": "Implants and casting materials"},
    {"name": "Anesthesia", "description": "Masks, tubes, and circuits"},
]

category_obj_map = {}
for cat in categories_data:
    obj, created = Category.objects.get_or_create(name=cat['name'], defaults={'description': cat['description']})
    category_obj_map[cat['name']] = obj

products_data = [
    # Disposables
    {"name": "Surgical Gloves (Size 7)", "category_name": "Disposables", "description": "High-quality latex, powder-free.", "mrp": 250.00, "selling_price": 180.00, "stock_quantity": 500, "gst_rate": 5.00, "image_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&q=80&w=400"},
    {"name": "IV Cannula 20G", "category_name": "Disposables", "description": "Pink IV Cannula with wings.", "mrp": 45.00, "selling_price": 32.00, "stock_quantity": 1200, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&q=80&w=400"},
    {"name": "Syringe 5ml with Needle", "category_name": "Disposables", "description": "Box of 100 single-use syringes.", "mrp": 500.00, "selling_price": 380.00, "stock_quantity": 300, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1579152276502-54523f0367eb?auto=format&fit=crop&q=80&w=400"},
    
    # Diagnostics
    {"name": "Digital Thermometer", "category_name": "Diagnostics", "description": "Fast and accurate LCD display.", "mrp": 450.00, "selling_price": 320.00, "stock_quantity": 50, "gst_rate": 18.00, "image_url": "https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?auto=format&fit=crop&q=80&w=400"},
    {"name": "Blood Pressure Monitor", "category_name": "Diagnostics", "description": "Automatic upper arm BP monitor.", "mrp": 2800.00, "selling_price": 1950.00, "stock_quantity": 15, "gst_rate": 18.00, "image_url": "https://images.unsplash.com/photo-1628177142898-93e36e4e3a50?auto=format&fit=crop&q=80&w=400"},
    {"name": "Pulse Oximeter", "category_name": "Diagnostics", "description": "Fingertip oxygen saturation monitor.", "mrp": 1500.00, "selling_price": 950.00, "stock_quantity": 40, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&q=80&w=400"},

    # Protection
    {"name": "N95 Respirator Mask", "category_name": "Protection", "description": "Pack of 10 high filtration masks.", "mrp": 1200.00, "selling_price": 850.00, "stock_quantity": 100, "gst_rate": 5.00, "image_url": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&q=80&w=400"},
    {"name": "Face Shield Professional", "category_name": "Protection", "description": "Anti-fog adjustable face shield.", "mrp": 150.00, "selling_price": 95.00, "stock_quantity": 250, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1584467735815-f778f274e296?auto=format&fit=crop&q=80&w=400"},
    
    # Instruments
    {"name": "Surgical Scalpel Handle #3", "category_name": "Instruments", "description": "Stainless steel precision handle.", "mrp": 650.00, "selling_price": 490.00, "stock_quantity": 25, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1579152276502-54523f0367eb?auto=format&fit=crop&q=80&w=400"},
    {"name": "Mayo Scissors 6.75inch", "category_name": "Instruments", "description": "Curved surgical scissors.", "mrp": 1200.00, "selling_price": 850.00, "stock_quantity": 12, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1512678080530-7760d81faba6?auto=format&fit=crop&q=80&w=400"},

    # Sutures
    {"name": "Vicryl 2-0 Suture", "category_name": "Sutures", "description": "Absorbable braided suture.", "mrp": 4500.00, "selling_price": 3800.00, "stock_quantity": 20, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1612719293148-5256e299105c?auto=format&fit=crop&q=80&w=400"},
    {"name": "Silk 3-0 Suture", "category_name": "Sutures", "description": "Non-absorbable black braided silk.", "mrp": 3200.00, "selling_price": 2600.00, "stock_quantity": 30, "gst_rate": 12.00, "image_url": "https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&q=80&w=400"},

    # Wound Care
    {"name": "Adhesive Gauze 10x10cm", "category_name": "Wound Care", "description": "Sterile adhesive wound dressing.", "mrp": 80.00, "selling_price": 55.00, "stock_quantity": 1000, "gst_rate": 5.00, "image_url": "https://images.unsplash.com/photo-1583947581924-860bda6a26df?auto=format&fit=crop&q=80&w=400"},
    {"name": "Crepe Bandage 10cm", "category_name": "Wound Care", "description": "Stretchable support bandage.", "mrp": 120.00, "selling_price": 85.00, "stock_quantity": 400, "gst_rate": 5.00, "image_url": "https://images.unsplash.com/photo-1603398938378-e54eab446f90?auto=format&fit=crop&q=80&w=400"},
]

for p in products_data:
    cat_name = p.pop('category_name')
    p['category'] = category_obj_map[cat_name]
    Product.objects.update_or_create(name=p['name'], defaults=p)

# Create Mock Pharmacies
pharmacies_data = [
    {
        "pharmacy_name": "City Life Pharmacy",
        "license_number": "DL/123/2024",
        "gst_number": "07AAAAA0000A1Z5",
        "contact_person": "Rahul Sharma",
        "phone": "9876543210",
        "email": "citylife@example.com",
        "address": "12, Main Market, New Delhi"
    },
    {
        "pharmacy_name": "Aman Medicos",
        "license_number": "MH/456/2024",
        "gst_number": "27BBBBB0000B1Z6",
        "contact_person": "Mohit Gupta",
        "phone": "9123456789",
        "email": "aman@example.com",
        "address": "Shop 4, Station Road, Mumbai"
    }
]

# Helper for users to ensure they exist with correct role/pharmacy
def ensure_user(email, password, role, pharmacy=None):
    user = User.objects.filter(email=email).first()
    is_admin = (role == 'admin')
    if not user:
        user = User.objects.create_user(
            username=email, 
            email=email, 
            password=password, 
            role=role, 
            pharmacy=pharmacy,
            is_staff=is_admin,
            is_superuser=is_admin
        )
    else:
        user.role = role
        user.pharmacy = pharmacy
        user.is_staff = is_admin
        user.is_superuser = is_admin
        user.set_password(password)
        user.save()
    return user

for ph_data in pharmacies_data:
    ph, created = Pharmacy.objects.get_or_create(pharmacy_name=ph_data['pharmacy_name'], defaults=ph_data)
    ensure_user(ph_data['email'], 'pharmacypassword', 'pharmacy', ph)

# Ensure our specific admin exists
ensure_user('admin@surgicaldistro.com', 'adminpassword', 'admin')

# Cleanup old admin if it exists with wrong email/username
User.objects.filter(username='admin', email='admin@example.com').delete()

print("Seed data updated successfully with correct credentials!")
