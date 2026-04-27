#!/usr/bin/env python3
"""
Seed script: create 50 realistic Malaysian customers.

Distribution: 30 B2B (corporate) + 20 B2C (individual)
B2B TIN: C + 10 digits
B2C TIN: 12-digit NRIC format YYMMDDPPXXXX (PP = state code)

Run inside the container:
  docker compose exec backend python scripts/seed_customers.py

Idempotent: safe to re-run; existing records (by code) are skipped.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.enums import CustomerType
from app.models.partner import Customer

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# B2B Customers (30)
# Each dict:
#   code, name, tin, registration_no, customer_type="B2B",
#   address_line1, city, state, postcode, country,
#   phone, email, contact_person,
#   currency_code, payment_terms_days, credit_limit_str
# ---------------------------------------------------------------------------

B2B_CUSTOMERS: list[dict] = [
    # ── Hypermarkets / Chains (1-5) ─────────────────────────────────────────
    {
        "code": "CUS-001",
        "name": "Sunrise Hypermart Sdn Bhd",
        "tin": "C1111222233",
        "registration_no": "20050115543",
        "address_line1": "Lot G-1, Mid Valley Megamall",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "59200",
        "phone": "+60 3-2284 1111",
        "email": "procurement@sunrisehypermart.com.my",
        "contact_person": "Lim Ah Kow",
        "payment_terms_days": 30,
        "credit_limit": "200000.00",
    },
    {
        "code": "CUS-002",
        "name": "Megamart Retail Group Sdn Bhd",
        "tin": "C2222333344",
        "registration_no": "20030620876",
        "address_line1": "No. 1, Jalan Imbi",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "55100",
        "phone": "+60 3-2142 2222",
        "email": "purchasing@megamart.com.my",
        "contact_person": "Tan Wei Ming",
        "payment_terms_days": 30,
        "credit_limit": "150000.00",
    },
    {
        "code": "CUS-003",
        "name": "Family Mart Franchise Sdn Bhd",
        "tin": "C3333444455",
        "registration_no": "20100810234",
        "address_line1": "Jalan Maharajalela, Brickfields",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50480",
        "phone": "+60 3-2274 3333",
        "email": "ops@familymartmy.com.my",
        "contact_person": "Wong Siew Lin",
        "payment_terms_days": 45,
        "credit_limit": "100000.00",
    },
    {
        "code": "CUS-004",
        "name": "Penang Superstore Chain Sdn Bhd",
        "tin": "C4444555566",
        "registration_no": "20010305765",
        "address_line1": "No. 55, Jalan Burma",
        "city": "Georgetown",
        "state": "Pulau Pinang",
        "postcode": "10350",
        "phone": "+60 4-228 4444",
        "email": "purchasing@penangsuperstore.com.my",
        "contact_person": "Cheah Boon Hock",
        "payment_terms_days": 30,
        "credit_limit": "80000.00",
    },
    {
        "code": "CUS-005",
        "name": "JB Retailer Network Sdn Bhd",
        "tin": "C5555666677",
        "registration_no": "20080415432",
        "address_line1": "No. 8, Jalan Wong Ah Fook",
        "city": "Johor Bahru",
        "state": "Johor",
        "postcode": "80000",
        "phone": "+60 7-223 5555",
        "email": "order@jbretailnet.com.my",
        "contact_person": "Ong Teck Hwa",
        "payment_terms_days": 30,
        "credit_limit": "90000.00",
    },
    # ── Restaurants / F&B (6-13) ────────────────────────────────────────────
    {
        "code": "CUS-006",
        "name": "Restoran Nasi Lemak Pak Ali Sdn Bhd",
        "tin": "C6666777788",
        "registration_no": "20060915123",
        "address_line1": "No. 12, Jalan Tuanku Abdul Halim",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50480",
        "phone": "+60 3-4042 6666",
        "email": "restoran.pakali@gmail.com",
        "contact_person": "Ali bin Abu Bakar",
        "payment_terms_days": 14,
        "credit_limit": "15000.00",
    },
    {
        "code": "CUS-007",
        "name": "Dragon Palace Restaurant Sdn Bhd",
        "tin": "C7777888899",
        "registration_no": "20120220876",
        "address_line1": "Lot 2.18, The Gardens Mall",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "59200",
        "phone": "+60 3-2282 7777",
        "email": "dragonpalace@gmail.com",
        "contact_person": "Michael Leong Chian Kiat",
        "payment_terms_days": 14,
        "credit_limit": "20000.00",
    },
    {
        "code": "CUS-008",
        "name": "Kopitiam Ventures Sdn Bhd",
        "tin": "C8888999900",
        "registration_no": "20091015543",
        "address_line1": "No. 33, Jalan Tun Razak",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50400",
        "phone": "+60 3-2161 8888",
        "email": "kopitiam.ventures@yahoo.com",
        "contact_person": "Cindy Yap Siew Ching",
        "payment_terms_days": 14,
        "credit_limit": "12000.00",
    },
    {
        "code": "CUS-009",
        "name": "Mamak Corner Holdings Sdn Bhd",
        "tin": "C9999000011",
        "registration_no": "20070710432",
        "address_line1": "No. 6, Jalan Gombak",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "53000",
        "phone": "+60 3-4023 9999",
        "email": "mamakcorner@gmail.com",
        "contact_person": "Selvam a/l Krishnan",
        "payment_terms_days": 14,
        "credit_limit": "10000.00",
    },
    {
        "code": "CUS-010",
        "name": "Warung Mak Som Enterprise",
        "tin": "C1010101010",
        "registration_no": "20140520234",
        "address_line1": "No. 2, Kampung Baru",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50460",
        "phone": "+60 3-2694 1010",
        "email": "warungmaksom@gmail.com",
        "contact_person": "Somiati binti Rahmat",
        "payment_terms_days": 14,
        "credit_limit": "8000.00",
    },
    {
        "code": "CUS-011",
        "name": "Penang Char Koay Teow Co Sdn Bhd",
        "tin": "C2020202020",
        "registration_no": "20050615765",
        "address_line1": "No. 14, Lorong Selamat",
        "city": "Georgetown",
        "state": "Pulau Pinang",
        "postcode": "10400",
        "phone": "+60 4-226 2020",
        "email": "pgcharkoay@gmail.com",
        "contact_person": "Ah Huat (Tan Boon Huat)",
        "payment_terms_days": 14,
        "credit_limit": "10000.00",
    },
    {
        "code": "CUS-012",
        "name": "Cendol & Ais Batu Sdn Bhd",
        "tin": "C3030303030",
        "registration_no": "20160915432",
        "address_line1": "No. 28, Jalan Hang Lekir",
        "city": "Melaka",
        "state": "Melaka",
        "postcode": "75000",
        "phone": "+60 6-282 3030",
        "email": "cendol.batu@gmail.com",
        "contact_person": "Raja Aziz bin Raja Daud",
        "payment_terms_days": 14,
        "credit_limit": "7000.00",
    },
    {
        "code": "CUS-013",
        "name": "Happy Garden Dim Sum Restaurant",
        "tin": "C4040404040",
        "registration_no": "20030420123",
        "address_line1": "No. 20, Jalan Kuchai Lama",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "58200",
        "phone": "+60 3-7984 4040",
        "email": "happygarden.dimsum@gmail.com",
        "contact_person": "Ng Ah Moi",
        "payment_terms_days": 14,
        "credit_limit": "12000.00",
    },
    # ── Office Procurement / Corporate (14-21) ──────────────────────────────
    {
        "code": "CUS-014",
        "name": "Teknologi Sinergi Sdn Bhd",
        "tin": "C5050505050",
        "registration_no": "20130615876",
        "address_line1": "Level 18, Menara TM, Jalan Pantai Baharu",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50672",
        "phone": "+60 3-2240 5050",
        "email": "procurement@teksin.com.my",
        "contact_person": "Ahmad Fauzi bin Zakaria",
        "payment_terms_days": 30,
        "credit_limit": "50000.00",
    },
    {
        "code": "CUS-015",
        "name": "Global Services Malaysia Sdn Bhd",
        "tin": "C6060606060",
        "registration_no": "20091010543",
        "address_line1": "Suite 9.1, Level 9, Menara Worldwide",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50450",
        "phone": "+60 3-2718 6060",
        "email": "admin@globalservicesmy.com",
        "contact_person": "Karen Loh Wai Mun",
        "payment_terms_days": 30,
        "credit_limit": "40000.00",
    },
    {
        "code": "CUS-016",
        "name": "Agensi Pengiklanan Kreatif Sdn Bhd",
        "tin": "C7070707070",
        "registration_no": "20150225432",
        "address_line1": "No. 6, Jalan Delima 1/3, Subang Hi-Tech",
        "city": "Shah Alam",
        "state": "Selangor",
        "postcode": "40150",
        "phone": "+60 3-5632 7070",
        "email": "office@kreatif.com.my",
        "contact_person": "Syed Hasan bin Syed Ali",
        "payment_terms_days": 30,
        "credit_limit": "25000.00",
    },
    {
        "code": "CUS-017",
        "name": "Sekolah Sri Nobel Sdn Bhd",
        "tin": "C8080808080",
        "registration_no": "20020815123",
        "address_line1": "No. 1, Jalan Sri Nobel, Pandan Mewah",
        "city": "Ampang",
        "state": "Selangor",
        "postcode": "68000",
        "phone": "+60 3-4297 8080",
        "email": "admin@srinobel.edu.my",
        "contact_person": "Pn. Zaharah binti Mohd Noor",
        "payment_terms_days": 30,
        "credit_limit": "20000.00",
    },
    {
        "code": "CUS-018",
        "name": "Klinik Keluarga Bestari Sdn Bhd",
        "tin": "C9090909090",
        "registration_no": "20170405765",
        "address_line1": "No. 15, Jalan Pandan Jaya 3/2",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "55100",
        "phone": "+60 3-4296 9090",
        "email": "klinik.bestari@gmail.com",
        "contact_person": "Dr. Lee Chin Hooi",
        "payment_terms_days": 30,
        "credit_limit": "30000.00",
    },
    {
        "code": "CUS-019",
        "name": "Koperasi Tentera Sdn Bhd",
        "tin": "C1122112211",
        "registration_no": "19961010321",
        "address_line1": "Kem Sungai Besi",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "57000",
        "phone": "+60 3-9074 1122",
        "email": "koperasi.tentera@gmail.com",
        "contact_person": "Sgt. Roslan bin Bakar",
        "payment_terms_days": 60,
        "credit_limit": "100000.00",
    },
    {
        "code": "CUS-020",
        "name": "PJ Corporate Supplies Sdn Bhd",
        "tin": "C2211221122",
        "registration_no": "20110320543",
        "address_line1": "No. 28, Jalan 17/45",
        "city": "Petaling Jaya",
        "state": "Selangor",
        "postcode": "46400",
        "phone": "+60 3-7956 2211",
        "email": "pj.corporate@gmail.com",
        "contact_person": "Howard Chan Keng Seng",
        "payment_terms_days": 30,
        "credit_limit": "35000.00",
    },
    {
        "code": "CUS-021",
        "name": "Universiti Teknologi Mara Berhad",
        "tin": "C3322332233",
        "registration_no": "19880615876",
        "address_line1": "40450 Shah Alam",
        "city": "Shah Alam",
        "state": "Selangor",
        "postcode": "40450",
        "phone": "+60 3-5544 3322",
        "email": "procurement@uitm.edu.my",
        "contact_person": "Encik Hairol Azrin bin Musa",
        "payment_terms_days": 60,
        "credit_limit": "200000.00",
    },
    # ── Clinics / Pharmacies (22-26) ────────────────────────────────────────
    {
        "code": "CUS-022",
        "name": "Farmasi Alpha Sdn Bhd",
        "tin": "C4433443344",
        "registration_no": "20080810432",
        "address_line1": "No. 1, Jalan Bangsar",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "59000",
        "phone": "+60 3-2282 4433",
        "email": "farmasi.alpha@gmail.com",
        "contact_person": "Pharmacist Wong Chee Kian",
        "payment_terms_days": 30,
        "credit_limit": "30000.00",
    },
    {
        "code": "CUS-023",
        "name": "Caring Pharmacy Group Sdn Bhd",
        "tin": "C5544554455",
        "registration_no": "20020920765",
        "address_line1": "No. 5, Jalan Kelang Lama",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "58000",
        "phone": "+60 3-7982 5544",
        "email": "caring.pharmacy@gmail.com",
        "contact_person": "Linda Goh Ah Lian",
        "payment_terms_days": 30,
        "credit_limit": "45000.00",
    },
    {
        "code": "CUS-024",
        "name": "Medipoint Healthcare Sdn Bhd",
        "tin": "C6655665566",
        "registration_no": "20130115234",
        "address_line1": "No. 10, Jalan PJU 1A/20B",
        "city": "Petaling Jaya",
        "state": "Selangor",
        "postcode": "47301",
        "phone": "+60 3-7805 6655",
        "email": "medipoint@gmail.com",
        "contact_person": "Dr. Priya Nair",
        "payment_terms_days": 30,
        "credit_limit": "35000.00",
    },
    {
        "code": "CUS-025",
        "name": "Klinik Desa Selangor",
        "tin": "C7766776677",
        "registration_no": "20061220543",
        "address_line1": "No. 3, Jalan Meru",
        "city": "Klang",
        "state": "Selangor",
        "postcode": "41050",
        "phone": "+60 3-3373 7766",
        "email": "klinik.desa.sel@gmail.com",
        "contact_person": "Dr. Hamdan bin Ismail",
        "payment_terms_days": 45,
        "credit_limit": "25000.00",
    },
    {
        "code": "CUS-026",
        "name": "Guardian Health & Beauty Sdn Bhd",
        "tin": "C8877887788",
        "registration_no": "20010415876",
        "address_line1": "Lot F1.16, Suria KLCC",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50088",
        "phone": "+60 3-2382 8877",
        "email": "guardian.klcc@guardian.com.my",
        "contact_person": "Jennifer Tan Sok Lin",
        "payment_terms_days": 30,
        "credit_limit": "60000.00",
    },
    # ── Factories / Manufacturers (27-30) ───────────────────────────────────
    {
        "code": "CUS-027",
        "name": "Paramount Manufacturing Sdn Bhd",
        "tin": "C9988998899",
        "registration_no": "20040615432",
        "address_line1": "PLO 55, Kawasan Perindustrian Pasir Gudang",
        "city": "Pasir Gudang",
        "state": "Johor",
        "postcode": "81700",
        "phone": "+60 7-252 9988",
        "email": "procurement@paramount-mfg.com.my",
        "contact_person": "Fong Kwok Yin",
        "payment_terms_days": 60,
        "credit_limit": "150000.00",
    },
    {
        "code": "CUS-028",
        "name": "Shah Alam Industrial Park Sdn Bhd",
        "tin": "C1001100110",
        "registration_no": "19980205123",
        "address_line1": "Lot 7, Seksyen 15, Hicom Industrial Park",
        "city": "Shah Alam",
        "state": "Selangor",
        "postcode": "40200",
        "phone": "+60 3-5519 1001",
        "email": "saip@gmail.com",
        "contact_person": "Roslan bin Majid",
        "payment_terms_days": 60,
        "credit_limit": "120000.00",
    },
    {
        "code": "CUS-029",
        "name": "Kilang Batu Pahat Sdn Bhd",
        "tin": "C2002200220",
        "registration_no": "20070515765",
        "address_line1": "Kawasan Perindustrian Batu Pahat, Jalan Air Panas",
        "city": "Batu Pahat",
        "state": "Johor",
        "postcode": "83000",
        "phone": "+60 7-432 2002",
        "email": "kilang.batupahat@gmail.com",
        "contact_person": "Eric Chong Beng Huat",
        "payment_terms_days": 60,
        "credit_limit": "80000.00",
    },
    {
        "code": "CUS-030",
        "name": "Ipoh Food Processing Sdn Bhd",
        "tin": "C3003300330",
        "registration_no": "20100820432",
        "address_line1": "Kawasan Perindustrian Meru",
        "city": "Ipoh",
        "state": "Perak",
        "postcode": "30020",
        "phone": "+60 5-527 3003",
        "email": "ipoh.foodproc@gmail.com",
        "contact_person": "Siti Aishah binti Murad",
        "payment_terms_days": 45,
        "credit_limit": "70000.00",
    },
]

# ---------------------------------------------------------------------------
# B2C Customers (20) — individual consumers
# TIN format: 12-digit NRIC (YYMMDD + 2-digit state code + 4 digits)
# ---------------------------------------------------------------------------

B2C_CUSTOMERS: list[dict] = [
    # Chinese Malaysians
    {
        "code": "CUS-031",
        "name": "Tan Ah Kow",
        "tin": "820314014567",
        "address_line1": "No. 3, Jalan Ampang",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50450",
        "phone": "+60 12-345 6789",
        "email": "tanakow@gmail.com",
    },
    {
        "code": "CUS-032",
        "name": "Lim Mei Ling",
        "tin": "900522104321",
        "address_line1": "No. 15, Jalan Damai",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "55000",
        "phone": "+60 16-234 5678",
        "email": "limml90@gmail.com",
    },
    {
        "code": "CUS-033",
        "name": "Wong Chee Keong",
        "tin": "751108016543",
        "address_line1": "No. 88, Taman Desa Jaya",
        "city": "Kepong",
        "state": "Kuala Lumpur",
        "postcode": "52100",
        "phone": "+60 11-3456 7890",
        "email": "wongck75@yahoo.com",
    },
    {
        "code": "CUS-034",
        "name": "Cheah Siew Ping",
        "tin": "950830105432",
        "address_line1": "No. 12, Jalan Cempaka",
        "city": "Petaling Jaya",
        "state": "Selangor",
        "postcode": "47810",
        "phone": "+60 17-567 8901",
        "email": "cheahsp95@gmail.com",
    },
    {
        "code": "CUS-035",
        "name": "Ng Boon Kee",
        "tin": "680420016789",
        "address_line1": "No. 6, Jalan Taman Kosas",
        "city": "Ampang",
        "state": "Selangor",
        "postcode": "68000",
        "phone": "+60 12-678 9012",
        "email": "ngbk68@hotmail.com",
    },
    {
        "code": "CUS-036",
        "name": "Koh Soo Ling",
        "tin": "881215105678",
        "address_line1": "No. 3, Jalan PJU 1A/4",
        "city": "Petaling Jaya",
        "state": "Selangor",
        "postcode": "47301",
        "phone": "+60 19-789 0123",
        "email": "kohsl88@gmail.com",
    },
    {
        "code": "CUS-037",
        "name": "Teh Weng Fai",
        "tin": "780305105678",
        "address_line1": "No. 20, Jalan Rebena 2, Bukit Rimau",
        "city": "Shah Alam",
        "state": "Selangor",
        "postcode": "40460",
        "phone": "+60 13-890 1234",
        "email": "tehwf78@gmail.com",
    },
    # Malay Malaysians
    {
        "code": "CUS-038",
        "name": "Muhammad Hafiz bin Abdullah",
        "tin": "920714016789",
        "address_line1": "No. 5, Jalan Setia Murni 4",
        "city": "Shah Alam",
        "state": "Selangor",
        "postcode": "40170",
        "phone": "+60 11-2345 6789",
        "email": "hafiz.abid@gmail.com",
    },
    {
        "code": "CUS-039",
        "name": "Siti Nurhaliza binti Tarudin",
        "tin": "870226016543",
        "address_line1": "No. 3, Jalan Cendana 9",
        "city": "Klang",
        "state": "Selangor",
        "postcode": "41000",
        "phone": "+60 14-345 6789",
        "email": "sitinur87@gmail.com",
    },
    {
        "code": "CUS-040",
        "name": "Ahmad Zahir bin Zainal",
        "tin": "830905016321",
        "address_line1": "No. 7, Jalan PU7/3",
        "city": "Puchong",
        "state": "Selangor",
        "postcode": "47100",
        "phone": "+60 12-456 7890",
        "email": "zahir.zainal83@gmail.com",
    },
    {
        "code": "CUS-041",
        "name": "Fauziah binti Ramli",
        "tin": "760412016987",
        "address_line1": "No. 18, Taman Melati",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "53100",
        "phone": "+60 17-567 8901",
        "email": "fauziah.ramli@yahoo.com",
    },
    {
        "code": "CUS-042",
        "name": "Khairul Anuar bin Musa",
        "tin": "910630016654",
        "address_line1": "Blok C-12-3, Residensi Seri Kembangan",
        "city": "Seri Kembangan",
        "state": "Selangor",
        "postcode": "43300",
        "phone": "+60 11-6789 0123",
        "email": "khairul.musa91@gmail.com",
    },
    {
        "code": "CUS-043",
        "name": "Norhayati binti Ibrahim",
        "tin": "841118016432",
        "address_line1": "No. 2, Jalan Kebun 21/13",
        "city": "Shah Alam",
        "state": "Selangor",
        "postcode": "40460",
        "phone": "+60 13-890 1234",
        "email": "norhayati.ib@gmail.com",
    },
    # Indian Malaysians
    {
        "code": "CUS-044",
        "name": "Rajesh a/l Krishnan",
        "tin": "880920016876",
        "address_line1": "No. 23, Jalan Satu Brickfields",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50470",
        "phone": "+60 16-901 2345",
        "email": "rajesh.krishnan88@gmail.com",
    },
    {
        "code": "CUS-045",
        "name": "Priya a/p Subramaniam",
        "tin": "940215016543",
        "address_line1": "No. 4, Jalan Maharajalela",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "50150",
        "phone": "+60 17-012 3456",
        "email": "priya.subra94@gmail.com",
    },
    {
        "code": "CUS-046",
        "name": "Murugesan a/l Pandian",
        "tin": "710530016876",
        "address_line1": "No. 12, Jalan Syed Putra",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "58000",
        "phone": "+60 12-123 4567",
        "email": "murugesan.pandian@gmail.com",
    },
    # Mix of cities
    {
        "code": "CUS-047",
        "name": "Lee Chin Wei",
        "tin": "960330071234",
        "address_line1": "No. 11, Jalan Utama",
        "city": "Georgetown",
        "state": "Pulau Pinang",
        "postcode": "10250",
        "phone": "+60 11-3456 7890",
        "email": "leecw96@gmail.com",
    },
    {
        "code": "CUS-048",
        "name": "Amirul Hakim bin Rashid",
        "tin": "010512011234",
        "address_line1": "No. 3, Jalan Bakar Bata",
        "city": "Alor Setar",
        "state": "Kedah",
        "postcode": "05050",
        "phone": "+60 14-567 8901",
        "email": "amirul.hakim@gmail.com",
    },
    {
        "code": "CUS-049",
        "name": "Tan Hui Ling",
        "tin": "891025011987",
        "address_line1": "No. 9, Jalan Harimau",
        "city": "Johor Bahru",
        "state": "Johor",
        "postcode": "80350",
        "phone": "+60 19-678 9012",
        "email": "tanhl89@gmail.com",
    },
    {
        "code": "CUS-050",
        "name": "Shanmugam a/l Vengatasamy",
        "tin": "720418016543",
        "address_line1": "No. 55, Taman Setapak Jaya",
        "city": "Kuala Lumpur",
        "state": "Kuala Lumpur",
        "postcode": "53300",
        "phone": "+60 12-789 0123",
        "email": "shanmugam.ven@gmail.com",
    },
]


async def seed_customers(session: AsyncSession) -> int:
    existing_result = await session.execute(select(Customer.code))
    existing_codes = {row[0] for row in existing_result.all()}

    from decimal import Decimal

    created = 0

    for cust in B2B_CUSTOMERS:
        if cust["code"] in existing_codes:
            log.info("customer_exists", code=cust["code"])
            continue

        customer = Customer(
            organization_id=1,
            code=cust["code"],
            name=cust["name"],
            customer_type=CustomerType.B2B,
            tin=cust["tin"],
            registration_no=cust.get("registration_no"),
            address_line1=cust["address_line1"],
            city=cust["city"],
            state=cust["state"],
            postcode=cust["postcode"],
            country="MY",
            phone=cust["phone"],
            email=cust["email"],
            contact_person=cust["contact_person"],
            currency="MYR",
            payment_terms_days=cust["payment_terms_days"],
            credit_limit=Decimal(cust["credit_limit"]),
            is_active=True,
        )
        session.add(customer)
        created += 1
        log.info("customer_created", code=cust["code"], type="B2B", name=cust["name"])

    for cust in B2C_CUSTOMERS:
        if cust["code"] in existing_codes:
            log.info("customer_exists", code=cust["code"])
            continue

        customer = Customer(
            organization_id=1,
            code=cust["code"],
            name=cust["name"],
            customer_type=CustomerType.B2C,
            tin=cust["tin"],
            registration_no=None,
            address_line1=cust["address_line1"],
            city=cust["city"],
            state=cust["state"],
            postcode=cust["postcode"],
            country="MY",
            phone=cust["phone"],
            email=cust.get("email"),
            contact_person=None,
            currency="MYR",
            payment_terms_days=0,
            credit_limit=Decimal("0.00"),
            is_active=True,
        )
        session.add(customer)
        created += 1
        log.info("customer_created", code=cust["code"], type="B2C", name=cust["name"])

    await session.flush()
    total = len(B2B_CUSTOMERS) + len(B2C_CUSTOMERS)
    log.info("customers_seeded", total=total, created=created, skipped=total - created)
    return created


async def main() -> None:
    import logging

    logging.basicConfig(level=logging.INFO)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        async with session.begin():
            created = await seed_customers(session)

    await engine.dispose()
    log.info("seed_complete", message=f"Customers seeded: {created} created.")
    print(f"\n✅ Seed complete — {created} customers created (existing skipped).")


if __name__ == "__main__":
    asyncio.run(main())
