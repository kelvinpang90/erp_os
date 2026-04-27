#!/usr/bin/env python3
"""
Seed script: 200 authentic Malaysian SKUs for ERP demo.

Categories: Beverages(30) | Instant Food(25) | Snacks(25) | Dairy(20)
            Cooking Essentials(20) | Rice/Oil(15) | Oral Care(8)
            Hair Care(7) | Skin Care(5) | Cleaning(10) | OTC Meds(15)
            Small Appliances(10) | Stationery(10)

Requires:
  seed_master_data.py   (org, users, warehouses)
  seed_reference_data.py (brands, categories, UOMs, tax_rates, MSIC codes)

Run:
  docker compose exec backend python scripts/seed_skus.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from decimal import ROUND_HALF_UP, Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.enums import CostingMethod
from app.models.master import Brand, Category, TaxRate, UOM
from app.models.organization import User
from app.models.sku import SKU

log = structlog.get_logger()

ORG_ID = 1

# ── Raw SKU data ───────────────────────────────────────────────────────────────
# (prefix, seq, name, name_zh, brand_code, cat_code, uom_code, tax_code,
#  price_excl_str, safety_stock, reorder_point, reorder_qty, msic_code)

RAW_SKUS: list[tuple] = [
    # ── Beverages (BEVER) ─────────────────────────────────────────────────────
    ("BEV",  1, "Milo 3-in-1 Original 30 Sticks",         "美禄三合一原味30条",        "MILO",      "BEVER",       "BOX",  "SST-10", "18.90",  30,  60, 120, "47210"),
    ("BEV",  2, "Milo 3-in-1 Less Sweet 15 Sticks",       "美禄三合一少甜15条",        "MILO",      "BEVER",       "BOX",  "SST-10",  "9.90",  30,  60, 120, "47210"),
    ("BEV",  3, "Milo Fuze 3-in-1 Original 30s",          "美禄Fuze三合一原味30条",    "MILO",      "BEVER",       "BOX",  "SST-10", "21.90",  20,  40,  80, "47210"),
    ("BEV",  4, "Milo Tin 400g",                          "美禄罐装400克",             "MILO",      "BEVER",       "PCS",  "SST-10", "11.90",  50, 100, 200, "47210"),
    ("BEV",  5, "Milo Tin 1kg",                           "美禄罐装1千克",             "MILO",      "BEVER",       "PCS",  "SST-10", "26.90",  30,  60, 120, "47210"),
    ("BEV",  6, "Nescafe 3-in-1 Original 30 Sticks",      "雀巢三合一原味30条",        "NESCAFE",   "BEVER",       "BOX",  "SST-10", "17.90",  30,  60, 120, "47210"),
    ("BEV",  7, "Nescafe 3-in-1 Less Sweet 25 Sticks",    "雀巢三合一少甜25条",        "NESCAFE",   "BEVER",       "BOX",  "SST-10", "14.90",  30,  60, 120, "47210"),
    ("BEV",  8, "Nescafe Classic Instant Coffee Jar 200g","雀巢经典速溶咖啡200克",     "NESCAFE",   "BEVER",       "PCS",  "SST-10", "22.90",  20,  40,  60, "47210"),
    ("BEV",  9, "Old Town White Coffee 3-in-1 Original 12s","旧街场白咖啡原味12包",   "OLDTOWN",   "BEVER",       "BOX",  "SST-10", "12.90",  30,  60, 120, "47210"),
    ("BEV", 10, "Old Town White Coffee Hazelnut 12s",     "旧街场白咖啡榛子味12包",   "OLDTOWN",   "BEVER",       "BOX",  "SST-10", "13.90",  20,  40,  80, "47210"),
    ("BEV", 11, "Aik Cheong White Coffee 3-in-1 15s",     "益昌白咖啡三合一15包",     "AIKCHEONG", "BEVER",       "BOX",  "SST-10", "13.50",  30,  60, 120, "47210"),
    ("BEV", 12, "Aik Cheong Hazelnut White Coffee 12s",   "益昌榛子白咖啡12包",       "AIKCHEONG", "BEVER",       "BOX",  "SST-10", "13.90",  20,  40,  80, "47210"),
    ("BEV", 13, "Boh Garden Tea Bags 25s",                "宝茶花园红茶25包",          "BOHTEA",    "BEVER",       "BOX",  "SST-10",  "5.90",  50, 100, 200, "47210"),
    ("BEV", 14, "Boh Cameronian Gold Blend 50 Bags",      "宝茶金牌混合茶50包",        "BOHTEA",    "BEVER",       "BOX",  "SST-10",  "9.90",  30,  60, 120, "47210"),
    ("BEV", 15, "Lipton Yellow Label Tea Bags 50s",       "立顿黄牌红茶50包",          "LIPTON",    "BEVER",       "BOX",  "SST-10",  "7.90",  40,  80, 160, "47210"),
    ("BEV", 16, "Coca-Cola Can 325ml",                    "可口可乐罐装325ml",         "COCACOLA",  "BEVER",       "PCS",  "SST-10",  "1.90", 200, 400, 800, "47210"),
    ("BEV", 17, "Coca-Cola 1.5L Bottle",                  "可口可乐瓶装1.5升",         "COCACOLA",  "BEVER",       "PCS",  "SST-10",  "3.90", 100, 200, 400, "47210"),
    ("BEV", 18, "Sprite Can 325ml",                       "雪碧罐装325ml",             "COCACOLA",  "BEVER",       "PCS",  "SST-10",  "1.90", 150, 300, 600, "47210"),
    ("BEV", 19, "100Plus Isotonic Drink Can 325ml",       "百加得运动饮料罐装325ml",   "ONEPLUS",   "BEVER",       "PCS",  "SST-10",  "1.90", 200, 400, 800, "47210"),
    ("BEV", 20, "100Plus 1.5L Bottle",                    "百加得瓶装1.5升",           "ONEPLUS",   "BEVER",       "PCS",  "SST-10",  "3.50", 100, 200, 400, "47210"),
    ("BEV", 21, "Yeo's Chrysanthemum Tea 300ml",          "杨协成菊花茶300ml",         "YEOS",      "BEVER",       "PCS",  "SST-10",  "1.80", 150, 300, 600, "47210"),
    ("BEV", 22, "Yeo's Soya Bean Drink 250ml",            "杨协成豆奶250ml",           "YEOS",      "BEVER",       "PCS",  "SST-10",  "1.60", 150, 300, 600, "47210"),
    ("BEV", 23, "Spritzer Mineral Water 1.5L",            "深山矿泉水1.5升",           "SPRITZER",  "BEVER",       "PCS",  "SST-10",  "2.20", 100, 200, 400, "47210"),
    ("BEV", 24, "Spritzer Sparkling Mineral Water 350ml", "深山气泡矿泉水350ml",       "SPRITZER",  "BEVER",       "PCS",  "SST-10",  "2.90",  80, 160, 320, "47210"),
    ("BEV", 25, "Vitagen Original Cultured Milk 5 × 125ml","优他健原味5瓶125ml",       "VITAGEN",   "BEVER",       "SET",  "SST-10",  "4.50",  60, 120, 240, "47210"),
    ("BEV", 26, "Vitagen Grape Cultured Milk 5 × 125ml",  "优他健葡萄味5瓶125ml",     "VITAGEN",   "BEVER",       "SET",  "SST-10",  "4.50",  60, 120, 240, "47210"),
    ("BEV", 27, "Dutch Lady Chocolate Drink 200ml",       "荷兰女郎巧克力饮料200ml",  "DUTCHLADY", "BEVER",       "PCS",  "SST-10",  "2.20", 100, 200, 400, "47210"),
    ("BEV", 28, "Dutch Lady Strawberry Drink 200ml",      "荷兰女郎草莓饮料200ml",    "DUTCHLADY", "BEVER",       "PCS",  "SST-10",  "2.20", 100, 200, 400, "47210"),
    ("BEV", 29, "Nescafe 3-in-1 Extra Caya 30s",          "雀巢三合一超香浓30条",      "NESCAFE",   "BEVER",       "BOX",  "SST-10", "18.90",  30,  60, 120, "47210"),
    ("BEV", 30, "Milo 3-in-1 Original 15 Sticks",         "美禄三合一原味15条",        "MILO",      "BEVER",       "BOX",  "SST-10",  "9.90",  30,  60, 120, "47210"),

    # ── Instant Food (INSTANT_FOOD) ───────────────────────────────────────────
    ("INF",  1, "Maggi Ayam Flavour Noodles 77g",         "美极鸡味面77克",            "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "0.80", 200, 400, 800, "47210"),
    ("INF",  2, "Maggi Kari Noodles 79g",                 "美极咖喱面79克",            "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "0.90", 200, 400, 800, "47210"),
    ("INF",  3, "Maggi Asam Laksa Noodles 100g",          "美极亚参叻沙面100克",       "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "2.10", 100, 200, 400, "47210"),
    ("INF",  4, "Maggi Tom Yam Kari 80g",                 "美极冬荫功咖喱80克",        "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "1.20", 150, 300, 600, "47210"),
    ("INF",  5, "Maggi Pedas Giler Ayam Bakar 89g",       "美极超辣烤鸡面89克",        "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "1.50", 100, 200, 400, "47210"),
    ("INF",  6, "Maggi Mee Goreng 80g",                   "美极炒面80克",              "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "0.90", 200, 400, 800, "47210"),
    ("INF",  7, "Maggi 2-Minute Noodles Pack 5s Chicken", "美极2分钟鸡味面5包装",      "MAGGI",     "INSTANT_FOOD","BOX",  "SST-10",  "3.90",  80, 160, 320, "47210"),
    ("INF",  8, "Maggi Kari Kapitan 80g",                 "美极嘉宾丹咖喱面80克",      "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "1.40", 100, 200, 400, "47210"),
    ("INF",  9, "Mamee Chef Chicken Noodles 80g",         "妈咪厨房鸡味面80克",        "MAMEE",     "INSTANT_FOOD","PCS",  "SST-10",  "1.20", 150, 300, 600, "47210"),
    ("INF", 10, "Mamee Chef Tom Yam 83g",                 "妈咪厨房冬荫功83克",        "MAMEE",     "INSTANT_FOOD","PCS",  "SST-10",  "1.50", 100, 200, 400, "47210"),
    ("INF", 11, "Mamee Chef Laksa 80g",                   "妈咪厨房叻沙面80克",        "MAMEE",     "INSTANT_FOOD","PCS",  "SST-10",  "1.50", 100, 200, 400, "47210"),
    ("INF", 12, "Mamee Chef Asam Laksa 80g",              "妈咪厨房亚参叻沙80克",      "MAMEE",     "INSTANT_FOOD","PCS",  "SST-10",  "2.00",  80, 160, 320, "47210"),
    ("INF", 13, "Cintan Ayam Noodles 75g",                "金汤鸡味面75克",            "CINTAN",    "INSTANT_FOOD","PCS",  "SST-10",  "0.75", 200, 400, 800, "47210"),
    ("INF", 14, "Cintan Curry Noodles 75g",               "金汤咖喱面75克",            "CINTAN",    "INSTANT_FOOD","PCS",  "SST-10",  "0.75", 200, 400, 800, "47210"),
    ("INF", 15, "Cintan Tom Yam 75g",                     "金汤冬荫功75克",            "CINTAN",    "INSTANT_FOOD","PCS",  "SST-10",  "0.90", 150, 300, 600, "47210"),
    ("INF", 16, "Cintan Chicken 5-Pack",                  "金汤鸡味面5包装",           "CINTAN",    "INSTANT_FOOD","BOX",  "SST-10",  "3.50",  80, 160, 320, "47210"),
    ("INF", 17, "MyKuali Penang White Curry Noodle 110g", "马奎槟城白咖喱面110克",     "MYKUALI",   "INSTANT_FOOD","PCS",  "SST-10",  "3.90",  50, 100, 200, "47210"),
    ("INF", 18, "MyKuali Penang Asam Laksa 106g",         "马奎槟城亚参叻沙106克",     "MYKUALI",   "INSTANT_FOOD","PCS",  "SST-10",  "3.90",  50, 100, 200, "47210"),
    ("INF", 19, "MyKuali Penang Prawn Noodle 110g",       "马奎槟城虾面110克",         "MYKUALI",   "INSTANT_FOOD","PCS",  "SST-10",  "4.20",  50, 100, 200, "47210"),
    ("INF", 20, "Indomie Goreng Original 85g",            "营多炒面原味85克",          "INDOMIE",   "INSTANT_FOOD","PCS",  "SST-10",  "0.85", 200, 400, 800, "47210"),
    ("INF", 21, "Indomie Rasa Kaldu Ayam 75g",            "营多鸡汤味75克",            "INDOMIE",   "INSTANT_FOOD","PCS",  "SST-10",  "0.80", 200, 400, 800, "47210"),
    ("INF", 22, "Indomie Ayam Bawang 75g",                "营多洋葱鸡味75克",          "INDOMIE",   "INSTANT_FOOD","PCS",  "SST-10",  "0.80", 200, 400, 800, "47210"),
    ("INF", 23, "Maggi Pedas Giler Tom Yam 89g",          "美极超辣冬荫功89克",        "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "1.50", 100, 200, 400, "47210"),
    ("INF", 24, "Mamee Monster Noodle Snack Chicken 25g", "妈咪怪兽零食鸡味25克",      "MAMEE",     "INSTANT_FOOD","PCS",  "SST-10",  "0.80", 300, 600,1200, "47210"),
    ("INF", 25, "Maggi Instant Rice Noodle Chicken 65g",  "美极鸡味即食米线65克",      "MAGGI",     "INSTANT_FOOD","PCS",  "SST-10",  "1.30", 100, 200, 400, "47210"),

    # ── Snacks (SNACK) ────────────────────────────────────────────────────────
    ("SNK",  1, "Mamee Double Decker Noodle Snack 20g",   "妈咪双层面零食20克",        "MAMEED",    "SNACK",       "PCS",  "SST-10",  "0.70", 300, 600,1200, "47210"),
    ("SNK",  2, "Mamee Double Decker BBQ 40g",            "妈咪双层烧烤味40克",        "MAMEED",    "SNACK",       "PCS",  "SST-10",  "1.10", 200, 400, 800, "47210"),
    ("SNK",  3, "Mamee Monster Cheese Snack 25g",         "妈咪怪兽芝士零食25克",      "MAMEED",    "SNACK",       "PCS",  "SST-10",  "0.80", 300, 600,1200, "47210"),
    ("SNK",  4, "Mamee Double Decker Box 12s",            "妈咪双层面12包装盒",        "MAMEED",    "SNACK",       "BOX",  "SST-10",  "7.90",  50, 100, 200, "47210"),
    ("SNK",  5, "Jack 'n Jill Nova BBQ Rings 60g",       "杰克阿吉烧烤圈60克",        "JACKNJILL", "SNACK",       "PCS",  "SST-10",  "2.90", 100, 200, 400, "47210"),
    ("SNK",  6, "Jack 'n Jill Roller Coaster Cheese 60g","杰克阿吉芝士60克",          "JACKNJILL", "SNACK",       "PCS",  "SST-10",  "2.90", 100, 200, 400, "47210"),
    ("SNK",  7, "Jack 'n Jill Nova 3D Rings 60g",        "杰克阿吉3D圆圈60克",        "JACKNJILL", "SNACK",       "PCS",  "SST-10",  "2.90", 100, 200, 400, "47210"),
    ("SNK",  8, "Twisties Chicken 60g",                   "扭扭鸡味60克",              "TWISTIES",  "SNACK",       "PCS",  "SST-10",  "2.90", 100, 200, 400, "47210"),
    ("SNK",  9, "Twisties Cheese 60g",                    "扭扭芝士60克",              "TWISTIES",  "SNACK",       "PCS",  "SST-10",  "2.90", 100, 200, 400, "47210"),
    ("SNK", 10, "Twisties BBQ Jumbo Pack 80g",            "扭扭烧烤大包80克",          "TWISTIES",  "SNACK",       "PCS",  "SST-10",  "3.90",  80, 160, 320, "47210"),
    ("SNK", 11, "Twisties Party Pack Chicken 160g",       "扭扭派对装鸡味160克",       "TWISTIES",  "SNACK",       "PCS",  "SST-10",  "6.90",  60, 120, 240, "47210"),
    ("SNK", 12, "Oreo Original Biscuit 119.6g",           "奥利奥原味饼干119.6克",     "OREO",      "SNACK",       "PCS",  "SST-10",  "4.50",  80, 160, 320, "47210"),
    ("SNK", 13, "Oreo Chocolate Cream Biscuit 137g",      "奥利奥巧克力饼干137克",     "OREO",      "SNACK",       "PCS",  "SST-10",  "4.90",  80, 160, 320, "47210"),
    ("SNK", 14, "Oreo Golden Biscuit 154g",               "奥利奥金色饼干154克",       "OREO",      "SNACK",       "PCS",  "SST-10",  "5.90",  60, 120, 240, "47210"),
    ("SNK", 15, "Oreo Mini Snack Pack 20g",               "奥利奥迷你小包20克",        "OREO",      "SNACK",       "PCS",  "SST-10",  "1.20", 200, 400, 800, "47210"),
    ("SNK", 16, "High-5 White Sandwich Bread 400g",       "高5白面包400克",            "HIGH5",     "SNACK",       "PCS",  "SST-10",  "4.20", 100, 200, 400, "47210"),
    ("SNK", 17, "High-5 Wholemeal Bread 400g",            "高5全麦面包400克",          "HIGH5",     "SNACK",       "PCS",  "SST-10",  "4.50",  80, 160, 320, "47210"),
    ("SNK", 18, "High-5 Roti Sandwich 72g",               "高5三明治72克",             "HIGH5",     "SNACK",       "PCS",  "SST-10",  "1.50", 200, 400, 800, "47210"),
    ("SNK", 19, "Gardenia Original Classic Bread 400g",   "家顿经典原味面包400克",     "GARDENIA",  "SNACK",       "PCS",  "SST-10",  "4.50", 100, 200, 400, "47210"),
    ("SNK", 20, "Gardenia Butterscotch Bread 400g",       "家顿奶油糖果面包400克",     "GARDENIA",  "SNACK",       "PCS",  "SST-10",  "4.90",  80, 160, 320, "47210"),
    ("SNK", 21, "Gardenia Toast Bread 450g",              "家顿吐司面包450克",         "GARDENIA",  "SNACK",       "PCS",  "SST-10",  "5.50",  80, 160, 320, "47210"),
    ("SNK", 22, "Gardenia Raisin Loaf 400g",              "家顿葡萄干面包400克",       "GARDENIA",  "SNACK",       "PCS",  "SST-10",  "5.50",  60, 120, 240, "47210"),
    ("SNK", 23, "Julie's Love Letter 700g",               "朱莉爱情信纸饼干700克",     "JULIES",    "SNACK",       "PCS",  "SST-10",  "9.90",  50, 100, 200, "47210"),
    ("SNK", 24, "Julie's Biscuit Rolls Peanut Butter 126g","朱莉花生酱卷饼126克",      "JULIES",    "SNACK",       "PCS",  "SST-10",  "5.90",  60, 120, 240, "47210"),
    ("SNK", 25, "Julie's Cheese Crackers 160g",           "朱莉芝士饼干160克",         "JULIES",    "SNACK",       "PCS",  "SST-10",  "6.50",  60, 120, 240, "47210"),

    # ── Dairy (DAIRY) ─────────────────────────────────────────────────────────
    ("DAI",  1, "Dutch Lady UHT Full Cream Milk 1L",      "荷兰女郎全脂牛奶1升",       "DUTCHLADY", "DAIRY",       "PCS",  "SST-0",   "6.90", 100, 200, 400, "47210"),
    ("DAI",  2, "Dutch Lady UHT Low Fat Milk 1L",         "荷兰女郎低脂牛奶1升",       "DUTCHLADY", "DAIRY",       "PCS",  "SST-0",   "7.20",  80, 160, 320, "47210"),
    ("DAI",  3, "Dutch Lady UHT Skimmed Milk 1L",         "荷兰女郎脱脂牛奶1升",       "DUTCHLADY", "DAIRY",       "PCS",  "SST-0",   "7.50",  60, 120, 240, "47210"),
    ("DAI",  4, "Dutch Lady UHT Milk 6 × 250ml",         "荷兰女郎牛奶6瓶250ml",      "DUTCHLADY", "DAIRY",       "SET",  "SST-0",  "11.90",  60, 120, 240, "47210"),
    ("DAI",  5, "Dutch Lady Plain Yoghurt 140g",          "荷兰女郎原味酸奶140克",     "DUTCHLADY", "DAIRY",       "PCS",  "SST-10",  "3.20",  80, 160, 320, "47210"),
    ("DAI",  6, "Dutch Lady Strawberry Yoghurt 140g",     "荷兰女郎草莓酸奶140克",     "DUTCHLADY", "DAIRY",       "PCS",  "SST-10",  "3.20",  80, 160, 320, "47210"),
    ("DAI",  7, "Dutch Lady Chocolate Flavoured Milk 200ml","荷兰女郎巧克力奶200ml",   "DUTCHLADY", "DAIRY",       "PCS",  "SST-10",  "2.20", 100, 200, 400, "47210"),
    ("DAI",  8, "Dutch Lady Growing Up Milk 1+ 900g",     "荷兰女郎成长奶粉1段900克",  "DUTCHLADY", "DAIRY",       "PCS",  "SST-0",  "42.90",  20,  40,  60, "47210"),
    ("DAI",  9, "Farm Fresh UHT Full Cream Milk 1L",      "农场新鲜全脂牛奶1升",       "FARMFRESH", "DAIRY",       "PCS",  "SST-0",   "7.50",  80, 160, 320, "47210"),
    ("DAI", 10, "Farm Fresh Fresh Milk 1L",               "农场新鲜鲜奶1升",           "FARMFRESH", "DAIRY",       "PCS",  "SST-0",   "8.90",  60, 120, 240, "47210"),
    ("DAI", 11, "Farm Fresh UHT Milk 6 × 200ml",         "农场新鲜牛奶6瓶200ml",      "FARMFRESH", "DAIRY",       "SET",  "SST-0",   "9.90",  50, 100, 200, "47210"),
    ("DAI", 12, "Farm Fresh Chocolate Flavoured Milk 200ml","农场新鲜巧克力奶200ml",   "FARMFRESH", "DAIRY",       "PCS",  "SST-10",  "2.50", 100, 200, 400, "47210"),
    ("DAI", 13, "Farm Fresh Mango Yoghurt 140g",          "农场新鲜芒果酸奶140克",     "FARMFRESH", "DAIRY",       "PCS",  "SST-10",  "3.50",  60, 120, 240, "47210"),
    ("DAI", 14, "Farm Fresh Banana Yoghurt 140g",         "农场新鲜香蕉酸奶140克",     "FARMFRESH", "DAIRY",       "PCS",  "SST-10",  "3.50",  60, 120, 240, "47210"),
    ("DAI", 15, "Marigold UHT Full Cream Milk 1L",        "万紫千红全脂牛奶1升",       "MARIGOLD",  "DAIRY",       "PCS",  "SST-0",   "6.90",  80, 160, 320, "47210"),
    ("DAI", 16, "Marigold Sweetened Condensed Milk 380g", "万紫千红甜炼奶380克",       "MARIGOLD",  "DAIRY",       "PCS",  "SST-10",  "5.90",  60, 120, 240, "47210"),
    ("DAI", 17, "Marigold Plain Yoghurt 130g",            "万紫千红原味酸奶130克",     "MARIGOLD",  "DAIRY",       "PCS",  "SST-10",  "3.20",  60, 120, 240, "47210"),
    ("DAI", 18, "Marigold Full Cream Evaporated Milk 390g","万紫千红全脂淡奶390克",    "MARIGOLD",  "DAIRY",       "PCS",  "SST-10",  "5.90",  60, 120, 240, "47210"),
    ("DAI", 19, "F&N Magnolia UHT Milk 1L",              "F&N木兰全脂牛奶1升",        "FRNMAGNOLIA","DAIRY",      "PCS",  "SST-0",   "6.80",  80, 160, 320, "47210"),
    ("DAI", 20, "F&N Sweetened Condensed Milk 391g",      "F&N甜炼乳391克",            "FRNMAGNOLIA","DAIRY",      "PCS",  "SST-10",  "5.50",  60, 120, 240, "47210"),

    # ── Cooking Essentials (COOKING_ESS) ──────────────────────────────────────
    ("CKG",  1, "Knorr Chicken Seasoning Powder 1kg",     "家乐鸡粉1千克",             "KNORR",     "COOKING_ESS", "PCS",  "SST-10", "14.90",  30,  60, 120, "47210"),
    ("CKG",  2, "Knorr Chicken Stock Cube 8s",            "家乐鸡汤块8粒",             "KNORR",     "COOKING_ESS", "BOX",  "SST-10",  "3.90",  80, 160, 320, "47210"),
    ("CKG",  3, "Knorr Tomato Ketchup 325g",              "家乐番茄酱325克",           "KNORR",     "COOKING_ESS", "PCS",  "SST-10",  "6.50",  60, 120, 240, "47210"),
    ("CKG",  4, "Knorr Fish Sauce 700ml",                 "家乐鱼露700ml",             "KNORR",     "COOKING_ESS", "PCS",  "SST-10",  "9.90",  40,  80, 160, "47210"),
    ("CKG",  5, "Knorr Oyster Sauce 510g",                "家乐蚝油510克",             "KNORR",     "COOKING_ESS", "PCS",  "SST-10",  "8.90",  40,  80, 160, "47210"),
    ("CKG",  6, "Knorr Beef Stock Cube 8s",               "家乐牛肉汤块8粒",           "KNORR",     "COOKING_ESS", "BOX",  "SST-10",  "3.90",  60, 120, 240, "47210"),
    ("CKG",  7, "Ajinomoto Umami Seasoning 200g",         "味之素味精200克",           "AJINOMOTO", "COOKING_ESS", "PCS",  "SST-10",  "6.90",  50, 100, 200, "47210"),
    ("CKG",  8, "Ajinomoto AJI-SHIO Flavoured Salt 200g","味之素盐味200克",           "AJINOMOTO", "COOKING_ESS", "PCS",  "SST-10",  "4.90",  60, 120, 240, "47210"),
    ("CKG",  9, "Ajinomoto Perasa Ayam 1kg",              "味之素鸡精1千克",           "AJINOMOTO", "COOKING_ESS", "PCS",  "SST-10", "22.90",  20,  40,  80, "47210"),
    ("CKG", 10, "Baba's Meat Curry Powder 250g",          "巴巴肉咖喱粉250克",         "BABAS",     "COOKING_ESS", "PCS",  "SST-10",  "7.50",  40,  80, 160, "47210"),
    ("CKG", 11, "Baba's Fish Curry Powder 250g",          "巴巴鱼咖喱粉250克",         "BABAS",     "COOKING_ESS", "PCS",  "SST-10",  "7.50",  40,  80, 160, "47210"),
    ("CKG", 12, "Baba's Chicken Curry Powder 250g",       "巴巴鸡肉咖喱粉250克",       "BABAS",     "COOKING_ESS", "PCS",  "SST-10",  "7.50",  40,  80, 160, "47210"),
    ("CKG", 13, "Adabi Rempah Tumis Bawang 200g",         "阿达比炒葱香料200克",       "ADABI",     "COOKING_ESS", "PCS",  "SST-10",  "5.90",  40,  80, 160, "47210"),
    ("CKG", 14, "Adabi Sos Tiram Oyster Sauce 340g",      "阿达比蚝油340克",           "ADABI",     "COOKING_ESS", "PCS",  "SST-10",  "6.50",  40,  80, 160, "47210"),
    ("CKG", 15, "Adabi Perencah Nasi Goreng 200g",        "阿达比炒饭料200克",         "ADABI",     "COOKING_ESS", "PCS",  "SST-10",  "5.50",  50, 100, 200, "47210"),
    ("CKG", 16, "Adabi Cili Boh 200g",                    "阿达比辣椒酱200克",         "ADABI",     "COOKING_ESS", "PCS",  "SST-10",  "4.90",  50, 100, 200, "47210"),
    ("CKG", 17, "Kikkoman Soy Sauce 600ml",               "万字酱油600ml",             "KIKKOMAN",  "COOKING_ESS", "PCS",  "SST-10", "10.90",  40,  80, 160, "47210"),
    ("CKG", 18, "Kikkoman Sweet Soy Sauce 250ml",         "万字甜酱油250ml",           "KIKKOMAN",  "COOKING_ESS", "PCS",  "SST-10",  "7.50",  40,  80, 160, "47210"),
    ("CKG", 19, "Ajinomoto Mixed Spice 200g",             "味之素综合香料200克",        "AJINOMOTO", "COOKING_ESS", "PCS",  "SST-10",  "5.90",  40,  80, 160, "47210"),
    ("CKG", 20, "Baba's Sambal Belacan 200g",             "巴巴峇拉煎辣椒酱200克",     "BABAS",     "COOKING_ESS", "PCS",  "SST-10",  "6.90",  40,  80, 160, "47210"),

    # ── Rice, Oil & Flour (RICE_OIL) ──────────────────────────────────────────
    ("RCO",  1, "Jasmine Thai Hom Mali Fragrant Rice 5kg","茉莉泰国香米5千克",         "JASMINE",   "RICE_OIL",    "PCS",  "SST-0",  "24.90",  50, 100, 200, "47210"),
    ("RCO",  2, "Jasmine Thai Fragrant Rice 10kg",        "茉莉泰国香米10千克",        "JASMINE",   "RICE_OIL",    "PCS",  "SST-0",  "46.90",  30,  60, 120, "47210"),
    ("RCO",  3, "Jasmine Fragrant Rice 2kg",              "茉莉香米2千克",             "JASMINE",   "RICE_OIL",    "PCS",  "SST-0",  "10.90",  80, 160, 320, "47210"),
    ("RCO",  4, "Jasmine Glutinous Rice 1kg",             "茉莉糯米1千克",             "JASMINE",   "RICE_OIL",    "PCS",  "SST-0",   "5.90",  60, 120, 240, "47210"),
    ("RCO",  5, "Jasmine Premium Thai Jasmine Rice 5kg",  "茉莉精选泰国香米5千克",     "JASMINE",   "RICE_OIL",    "PCS",  "SST-0",  "28.90",  40,  80, 160, "47210"),
    ("RCO",  6, "Faiza Basmati Rice 5kg",                 "法依莎印度香米5千克",        "FAIZA",     "RICE_OIL",    "PCS",  "SST-0",  "32.90",  30,  60, 120, "47210"),
    ("RCO",  7, "Faiza Parboiled Rice 5kg",               "法依莎蒸谷米5千克",          "FAIZA",     "RICE_OIL",    "PCS",  "SST-0",  "22.90",  40,  80, 160, "47210"),
    ("RCO",  8, "Faiza Imported Thai Rice 5kg",           "法依莎泰国进口米5千克",      "FAIZA",     "RICE_OIL",    "PCS",  "SST-0",  "26.90",  40,  80, 160, "47210"),
    ("RCO",  9, "Sea Horse Cooking Oil 2L",               "海马食用油2升",             "SEAHORSE",  "RICE_OIL",    "PCS",  "SST-0",  "14.90",  60, 120, 240, "47210"),
    ("RCO", 10, "Sea Horse Cooking Oil 5L",               "海马食用油5升",             "SEAHORSE",  "RICE_OIL",    "PCS",  "SST-0",  "29.90",  40,  80, 160, "47210"),
    ("RCO", 11, "Sea Horse Palm Cooking Oil 3L",          "海马棕榈油3升",             "SEAHORSE",  "RICE_OIL",    "PCS",  "SST-0",  "18.90",  50, 100, 200, "47210"),
    ("RCO", 12, "Blue Key All Purpose Flour 1kg",         "蓝钥匙多用途面粉1千克",     "BLUEKEY",   "RICE_OIL",    "PCS",  "SST-0",   "3.90",  80, 160, 320, "47210"),
    ("RCO", 13, "Blue Key Self-Raising Flour 1kg",        "蓝钥匙自发面粉1千克",       "BLUEKEY",   "RICE_OIL",    "PCS",  "SST-0",   "4.20",  60, 120, 240, "47210"),
    ("RCO", 14, "Blue Key Bread Flour 1kg",               "蓝钥匙面包粉1千克",         "BLUEKEY",   "RICE_OIL",    "PCS",  "SST-0",   "4.90",  60, 120, 240, "47210"),
    ("RCO", 15, "Blue Key Corn Starch 500g",              "蓝钥匙玉米淀粉500克",       "BLUEKEY",   "RICE_OIL",    "PCS",  "SST-0",   "3.50",  80, 160, 320, "47210"),

    # ── Oral Care (ORAL_CARE) ─────────────────────────────────────────────────
    ("ORL",  1, "Colgate Total Whitening Toothpaste 200g","高露洁全效美白牙膏200克",   "COLGATE",   "ORAL_CARE",   "PCS",  "SST-10",  "9.90",  60, 120, 240, "47210"),
    ("ORL",  2, "Colgate Sensitive Pro-Relief 110g",      "高露洁抗敏感牙膏110克",     "COLGATE",   "ORAL_CARE",   "PCS",  "SST-10", "15.90",  40,  80, 160, "47210"),
    ("ORL",  3, "Colgate Herbal White Toothpaste 175g",   "高露洁草本美白牙膏175克",   "COLGATE",   "ORAL_CARE",   "PCS",  "SST-10",  "9.50",  60, 120, 240, "47210"),
    ("ORL",  4, "Colgate Extra Clean Toothbrush 2s",      "高露洁超净牙刷2支",         "COLGATE",   "ORAL_CARE",   "BOX",  "SST-10",  "7.90",  50, 100, 200, "47210"),
    ("ORL",  5, "Darlie All Shiny White Toothpaste 225g", "黑人全闪亮白牙膏225克",    "DARLIE",    "ORAL_CARE",   "PCS",  "SST-10",  "9.90",  60, 120, 240, "47210"),
    ("ORL",  6, "Darlie Double Action Herbal 225g",       "黑人双重草本牙膏225克",     "DARLIE",    "ORAL_CARE",   "PCS",  "SST-10",  "9.90",  60, 120, 240, "47210"),
    ("ORL",  7, "Darlie Charcoal Clean Toothpaste 160g",  "黑人活性炭牙膏160克",       "DARLIE",    "ORAL_CARE",   "PCS",  "SST-10", "12.50",  40,  80, 160, "47210"),
    ("ORL",  8, "Sensodyne Fresh Mint Toothpaste 100g",   "舒适达清新薄荷牙膏100克",   "SENSODYNE", "ORAL_CARE",   "PCS",  "SST-10", "18.90",  30,  60, 120, "47210"),

    # ── Hair Care (HAIR_CARE) ─────────────────────────────────────────────────
    ("HAI",  1, "Pantene Smooth & Sleek Shampoo 400ml",   "潘婷顺滑洗发水400ml",       "PANTENE",   "HAIR_CARE",   "PCS",  "SST-10", "14.90",  40,  80, 160, "47210"),
    ("HAI",  2, "Pantene Repair & Protect Shampoo 400ml", "潘婷修护洗发水400ml",       "PANTENE",   "HAIR_CARE",   "PCS",  "SST-10", "14.90",  40,  80, 160, "47210"),
    ("HAI",  3, "Pantene Total Damage Care Shampoo 400ml","潘婷全面修护洗发水400ml",   "PANTENE",   "HAIR_CARE",   "PCS",  "SST-10", "14.90",  40,  80, 160, "47210"),
    ("HAI",  4, "Pantene Conditioner Smooth 320ml",       "潘婷顺滑护发素320ml",       "PANTENE",   "HAIR_CARE",   "PCS",  "SST-10", "14.90",  40,  80, 160, "47210"),
    ("HAI",  5, "Head & Shoulders Classic Clean 400ml",   "海飞丝清爽去屑洗发水400ml", "HEADSHLD",  "HAIR_CARE",   "PCS",  "SST-10", "19.90",  40,  80, 160, "47210"),
    ("HAI",  6, "Head & Shoulders Citrus Fresh 400ml",    "海飞丝柑橘洗发水400ml",     "HEADSHLD",  "HAIR_CARE",   "PCS",  "SST-10", "19.90",  40,  80, 160, "47210"),
    ("HAI",  7, "Head & Shoulders Conditioner 320ml",     "海飞丝护发素320ml",         "HEADSHLD",  "HAIR_CARE",   "PCS",  "SST-10", "19.90",  30,  60, 120, "47210"),

    # ── Skin Care (SKIN_CARE) ─────────────────────────────────────────────────
    ("SKN",  1, "Dettol Original Bar Soap 110g",          "滴露原味香皂110克",         "DETTOL",    "SKIN_CARE",   "PCS",  "SST-10",  "3.90", 100, 200, 400, "47210"),
    ("SKN",  2, "Dettol Fresh Bar Soap 110g",             "滴露清新香皂110克",         "DETTOL",    "SKIN_CARE",   "PCS",  "SST-10",  "3.90", 100, 200, 400, "47210"),
    ("SKN",  3, "Dettol Antiseptic Liquid 250ml",         "滴露消毒液250ml",           "DETTOL",    "SKIN_CARE",   "PCS",  "SST-10",  "9.90",  60, 120, 240, "47210"),
    ("SKN",  4, "Lifebuoy Total 10 Soap Bar 80g × 4",    "卫宝全效香皂80克×4块",     "LIFEBUOY",  "SKIN_CARE",   "SET",  "SST-10",  "9.90",  50, 100, 200, "47210"),
    ("SKN",  5, "Lifebuoy Shampoo Daily Clean 340ml",     "卫宝日常清洁洗发水340ml",   "LIFEBUOY",  "SKIN_CARE",   "PCS",  "SST-10", "11.90",  40,  80, 160, "47210"),

    # ── Household Cleaning (CLEANING) ─────────────────────────────────────────
    ("CLN",  1, "Dynamo Power Gel Detergent 3.2kg",       "汰渍强力洁净洗衣粉3.2千克", "DYNAMO",    "CLEANING",    "PCS",  "SST-10", "29.90",  30,  60, 120, "47210"),
    ("CLN",  2, "Dynamo Liquid Detergent 3.5L",           "汰渍液体洗衣液3.5升",       "DYNAMO",    "CLEANING",    "PCS",  "SST-10", "32.90",  30,  60, 120, "47210"),
    ("CLN",  3, "Dynamo Antibacterial Detergent 3kg",     "汰渍抗菌洗衣粉3千克",       "DYNAMO",    "CLEANING",    "PCS",  "SST-10", "28.90",  30,  60, 120, "47210"),
    ("CLN",  4, "Breeze Clean & Fresh Detergent 2.5kg",   "碧浪清新洗衣粉2.5千克",     "BREEZE",    "CLEANING",    "PCS",  "SST-10", "26.90",  30,  60, 120, "47210"),
    ("CLN",  5, "Breeze Liquid Detergent 3L",             "碧浪液体洗衣液3升",         "BREEZE",    "CLEANING",    "PCS",  "SST-10", "29.90",  30,  60, 120, "47210"),
    ("CLN",  6, "Glade Automatic Spray Starter 269ml",    "佳雾空气清新剂套装269ml",   "GLADE",     "CLEANING",    "SET",  "SST-10", "24.90",  30,  60, 120, "47210"),
    ("CLN",  7, "Glade Plug-In Oil Refill 20ml",          "佳雾插电香氛补充装20ml",    "GLADE",     "CLEANING",    "PCS",  "SST-10", "11.90",  40,  80, 160, "47210"),
    ("CLN",  8, "Harpic Power Plus Toilet Cleaner 500ml", "哈碧强力厕清500ml",         "HARPIC",    "CLEANING",    "PCS",  "SST-10",  "9.90",  50, 100, 200, "47210"),
    ("CLN",  9, "Harpic Bathroom Cleaner 500ml",          "哈碧浴室清洁剂500ml",       "HARPIC",    "CLEANING",    "PCS",  "SST-10",  "9.90",  50, 100, 200, "47210"),
    ("CLN", 10, "Top Expert Liquid Detergent 3.6L",       "Top专家液体洗衣液3.6升",    "TOPCLEAN",  "CLEANING",    "PCS",  "SST-10", "29.90",  30,  60, 120, "47210"),

    # ── OTC Medication (OTC_MED) ──────────────────────────────────────────────
    ("OTC",  1, "Panadol Extra Tablet 24s",               "必理痛特效片24粒",          "PANADOL",   "OTC_MED",     "PCS",  "SST-0",   "6.90",  50, 100, 200, "47730"),
    ("OTC",  2, "Panadol Soluble Tablet 12s",             "必理痛溶片12粒",            "PANADOL",   "OTC_MED",     "PCS",  "SST-0",   "5.90",  50, 100, 200, "47730"),
    ("OTC",  3, "Panadol Extend Release 24s",             "必理痛缓释片24粒",          "PANADOL",   "OTC_MED",     "PCS",  "SST-0",   "9.90",  40,  80, 160, "47730"),
    ("OTC",  4, "Panadol Actifast Tablet 24s",            "必理痛速效片24粒",          "PANADOL",   "OTC_MED",     "PCS",  "SST-0",   "8.90",  40,  80, 160, "47730"),
    ("OTC",  5, "Panadol Cold & Flu 24s",                 "必理痛伤风感冒24粒",        "PANADOL",   "OTC_MED",     "PCS",  "SST-0",  "12.90",  30,  60, 120, "47730"),
    ("OTC",  6, "Strepsils Honey & Lemon 24s",            "使立消蜜糖柠檬24粒",        "STREPSILS", "OTC_MED",     "PCS",  "SST-0",   "8.90",  40,  80, 160, "47730"),
    ("OTC",  7, "Strepsils Original Lozenges 24s",        "使立消原味喉糖24粒",        "STREPSILS", "OTC_MED",     "PCS",  "SST-0",   "8.90",  40,  80, 160, "47730"),
    ("OTC",  8, "Strepsils Extra Cool Lozenges 16s",      "使立消超凉喉糖16粒",        "STREPSILS", "OTC_MED",     "PCS",  "SST-0",   "7.90",  40,  80, 160, "47730"),
    ("OTC",  9, "Vicks VapoRub Ointment 50g",             "维克斯伤风膏50克",          "VICKS",     "OTC_MED",     "PCS",  "SST-0",   "9.90",  40,  80, 160, "47730"),
    ("OTC", 10, "Vicks Formula 44 Cough Syrup 50ml",      "维克斯止咳液50ml",          "VICKS",     "OTC_MED",     "PCS",  "SST-0",   "8.90",  30,  60, 120, "47730"),
    ("OTC", 11, "Tiger Balm Regular White 19.4g",         "虎标万金油白色19.4克",      "TIGERBALM", "OTC_MED",     "PCS",  "SST-0",   "5.90",  60, 120, 240, "47730"),
    ("OTC", 12, "Tiger Balm Red Extra Strength 21g",      "虎标万金油红色21克",        "TIGERBALM", "OTC_MED",     "PCS",  "SST-0",   "6.90",  50, 100, 200, "47730"),
    ("OTC", 13, "Counterpain Cool Cream 120g",            "酸痛膏清凉型120克",         "COUNTERPAIN","OTC_MED",    "PCS",  "SST-0",  "12.90",  30,  60, 120, "47730"),
    ("OTC", 14, "Counterpain Analgesic Cream 60g",        "酸痛膏止痛60克",            "COUNTERPAIN","OTC_MED",    "PCS",  "SST-0",   "8.90",  40,  80, 160, "47730"),
    ("OTC", 15, "Eagle Brand Medicated Oil 24ml",         "老鹰标药油24ml",            "EAGLEBRAND","OTC_MED",     "PCS",  "SST-0",   "4.90",  60, 120, 240, "47730"),

    # ── Small Appliances (SMALL_APPL) ─────────────────────────────────────────
    ("APL",  1, "Pensonic Stand Fan 16 Inch PF-1607",     "Pensonic落地扇16寸",        "PENSONIC",  "SMALL_APPL",  "PCS",  "SST-10", "79.90",  10,  20,  40, "47591"),
    ("APL",  2, "Pensonic Table Fan 12 Inch PTF-1203",    "Pensonic台式风扇12寸",      "PENSONIC",  "SMALL_APPL",  "PCS",  "SST-10", "45.90",  15,  30,  60, "47591"),
    ("APL",  3, "Khind Stand Fan 16 Inch SF16D",          "Khind落地扇16寸",           "KHIND",     "SMALL_APPL",  "PCS",  "SST-10", "75.90",  10,  20,  40, "47591"),
    ("APL",  4, "Khind Table Fan 12 Inch TF12D",          "Khind台式风扇12寸",         "KHIND",     "SMALL_APPL",  "PCS",  "SST-10", "42.90",  15,  30,  60, "47591"),
    ("APL",  5, "Milux Table Fan 12 Inch MTF-120",        "Milux台式风扇12寸",         "MILUX",     "SMALL_APPL",  "PCS",  "SST-10", "39.90",  15,  30,  60, "47591"),
    ("APL",  6, "Panasonic Rice Cooker 1.8L SR-DF181",    "松下电饭锅1.8升",           "PANASON",   "SMALL_APPL",  "PCS",  "SST-10","149.90",  10,  20,  30, "47591"),
    ("APL",  7, "Khind Rice Cooker 1.0L RC310",           "Khind电饭锅1升",            "KHIND",     "SMALL_APPL",  "PCS",  "SST-10", "59.90",  15,  30,  40, "47591"),
    ("APL",  8, "Pensonic Rice Cooker 1.0L PRC-608",      "Pensonic电饭锅1升",         "PENSONIC",  "SMALL_APPL",  "PCS",  "SST-10", "55.90",  15,  30,  40, "47591"),
    ("APL",  9, "Panasonic Electric Kettle 1.8L NC-EG3000","松下电热水壶1.8升",        "PANASON",   "SMALL_APPL",  "PCS",  "SST-10", "89.90",  10,  20,  30, "47591"),
    ("APL", 10, "Khind Electric Kettle 1.8L EK1800",      "Khind电热水壶1.8升",        "KHIND",     "SMALL_APPL",  "PCS",  "SST-10", "59.90",  15,  30,  40, "47591"),

    # ── Stationery (STATIO) ───────────────────────────────────────────────────
    ("STA",  1, "Faber-Castell Grip 2001 HB Pencil 12s",  "辉柏嘉Grip2001 HB铅笔12支","FABERCAS",  "STATIO",      "BOX",  "SST-10",  "9.90",  40,  80, 160, "47990"),
    ("STA",  2, "Faber-Castell 1432 Ballpoint Pen Blue 12s","辉柏嘉圆珠笔蓝色12支",   "FABERCAS",  "STATIO",      "BOX",  "SST-10", "12.90",  30,  60, 120, "47990"),
    ("STA",  3, "Faber-Castell Whiteboard Marker Blue",    "辉柏嘉白板笔蓝色",         "FABERCAS",  "STATIO",      "PCS",  "SST-10",  "4.90",  60, 120, 240, "47990"),
    ("STA",  4, "Stabilo Boss Highlighter Yellow",         "Stabilo荧光笔黄色",         "STABILO",   "STATIO",      "PCS",  "SST-10",  "4.50",  80, 160, 320, "47990"),
    ("STA",  5, "Stabilo Boss Highlighter Set 4 Colours",  "Stabilo荧光笔4色套装",      "STABILO",   "STATIO",      "SET",  "SST-10", "15.90",  30,  60, 120, "47990"),
    ("STA",  6, "Campap A4 Copy Paper 80gsm 500 Sheets",   "Campap A4复印纸80克500张",  "CAMPAP",    "STATIO",      "BOX",  "SST-10", "18.90",  50, 100, 200, "47990"),
    ("STA",  7, "Campap A4 Copy Paper 75gsm 500 Sheets",   "Campap A4复印纸75克500张",  "CAMPAP",    "STATIO",      "BOX",  "SST-10", "16.90",  50, 100, 200, "47990"),
    ("STA",  8, "Campap Exercise Book A4 100 Pages",       "Campap A4练习本100页",      "CAMPAP",    "STATIO",      "PCS",  "SST-10",  "4.50",  80, 160, 320, "47990"),
    ("STA",  9, "UHU Stic Glue Stick 21g",                 "UHU固体胶棒21克",           "UHU",       "STATIO",      "PCS",  "SST-10",  "3.90",  60, 120, 240, "47990"),
    ("STA", 10, "UHU All Purpose Adhesive 35ml",           "UHU万能胶35ml",             "UHU",       "STATIO",      "PCS",  "SST-10",  "7.90",  50, 100, 200, "47990"),
]


# Category prefix → barcode base (9556 + 2-digit category index + 7-digit seq)
_CAT_INDEX = {
    "BEV": "01", "INF": "02", "SNK": "03", "DAI": "04",
    "CKG": "05", "RCO": "06", "ORL": "07", "HAI": "08",
    "SKN": "09", "CLN": "10", "OTC": "11", "APL": "12", "STA": "13",
}


def _build_barcode(prefix: str, seq: int) -> str:
    cat_idx = _CAT_INDEX.get(prefix, "00")
    return f"9556{cat_idx}{seq:07d}"


def _calc_incl_price(excl: str, tax_code: str) -> str:
    d = Decimal(excl)
    if tax_code == "SST-10":
        incl = (d * Decimal("1.10")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        incl = d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return str(incl)


# ── Seed logic ────────────────────────────────────────────────────────────────

async def _load_lookup_maps(session: AsyncSession) -> tuple[dict, dict, dict, dict]:
    brands = {b.code: b.id for b in (await session.execute(
        select(Brand).where(Brand.organization_id == ORG_ID, Brand.deleted_at.is_(None))
    )).scalars().all()}

    cats = {c.code: c.id for c in (await session.execute(
        select(Category).where(Category.organization_id == ORG_ID, Category.deleted_at.is_(None))
    )).scalars().all()}

    uoms = {u.code: u.id for u in (await session.execute(
        select(UOM).where(UOM.organization_id == ORG_ID)
    )).scalars().all()}

    tax_rates = {t.code: t.id for t in (await session.execute(
        select(TaxRate).where(TaxRate.organization_id == ORG_ID)
    )).scalars().all()}

    return brands, cats, uoms, tax_rates


async def _get_admin_user_id(session: AsyncSession) -> int:
    result = await session.execute(
        select(User).where(User.organization_id == ORG_ID, User.email == "admin@demo.my")
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise RuntimeError("admin@demo.my not found — run seed_master_data.py first")
    return user.id


async def seed_skus(session: AsyncSession) -> int:
    brands, cats, uoms, tax_rates = await _load_lookup_maps(session)
    admin_id = await _get_admin_user_id(session)

    existing = set(
        (await session.execute(
            select(SKU.code).where(SKU.organization_id == ORG_ID, SKU.deleted_at.is_(None))
        )).scalars().all()
    )

    created = 0
    for (prefix, seq, name, name_zh, brand_code, cat_code,
         uom_code, tax_code, price_excl, safety_stock,
         reorder_point, reorder_qty, msic_code) in RAW_SKUS:

        sku_code = f"SKU-{prefix}-{seq:04d}"
        if sku_code in existing:
            log.info("sku_exists", code=sku_code)
            continue

        brand_id = brands.get(brand_code)
        cat_id = cats.get(cat_code)
        uom_id = uoms.get(uom_code)
        tax_id = tax_rates.get(tax_code)

        if not all([brand_id, cat_id, uom_id, tax_id]):
            log.warning("sku_skip_missing_fk", code=sku_code,
                        brand=brand_code, cat=cat_code, uom=uom_code, tax=tax_code)
            continue

        price_incl = _calc_incl_price(price_excl, tax_code)

        sku = SKU(
            organization_id=ORG_ID,
            code=sku_code,
            barcode=_build_barcode(prefix, seq),
            name=name,
            name_zh=name_zh,
            brand_id=brand_id,
            category_id=cat_id,
            base_uom_id=uom_id,
            tax_rate_id=tax_id,
            msic_code=msic_code,
            unit_price_excl_tax=Decimal(price_excl),
            unit_price_incl_tax=Decimal(price_incl),
            price_tax_inclusive=False,
            costing_method=CostingMethod.WEIGHTED_AVERAGE,
            safety_stock=Decimal(str(safety_stock)),
            reorder_point=Decimal(str(reorder_point)),
            reorder_qty=Decimal(str(reorder_qty)),
            is_active=True,
            created_by=admin_id,
        )
        session.add(sku)
        created += 1
        log.info("sku_created", code=sku_code, name=name)

    await session.flush()
    return created


async def main() -> None:
    import logging
    logging.basicConfig(level=logging.INFO)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        async with session.begin():
            created = await seed_skus(session)

    await engine.dispose()
    print(f"\n✅ SKU seed complete: {created} created, {len(RAW_SKUS) - created} skipped (already exist)")


if __name__ == "__main__":
    asyncio.run(main())
