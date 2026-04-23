# SST Classification Guide (Malaysia Sales & Service Tax)

> 用于 seed 数据中 SKU 的 `tax_rate_id` 正确归类。参考 LHDN / Kastam 的 SST 分类规则。

## 三档 SST

| 档位 | 代码 | Rate | 适用 |
|---|---|---|---|
| **Sales Tax 10%** | `SST-10` | 10.00% | 大部分商品（默认） |
| **Service Tax 6%** | `SST-6` | 6.00% | 指定服务（餐饮、住宿、专业服务） |
| **Exempt** | `EXEMPT` | 0.00% | 药品 / 基本食品 / 教育 / 医疗 |

---

## 具体分类（seed SKU 时参考）

### 💊 Exempt (0%) — 零税率

**处方药与 OTC 药物**（关键词：mg / capsule / tablet / syrup / cream / ointment）：
- Panadol, Strepsils, Vicks VapoRub, Salonpas, Piriton, Zyrtec
- 降压药、糖尿病药、抗生素
- 维生素（如 Blackmores, Nutrilite）✅ Exempt

**基本食品**：
- 大米（Rice - Jasmine, Faiza, Sariwangi）
- 食用油（Cooking Oil - Sea Horse, Daily, Knife）
- 面粉（Flour - Blue Key, Cap Sauh）
- 糖（Sugar - Gula Prai）
- 食盐
- 鸡蛋
- 新鲜蔬菜 / 新鲜水果 / 新鲜肉类 / 新鲜鱼类
- 婴儿奶粉（Friso, Similac, Enfamil, Dumex 婴幼儿阶段）

**书籍 / 报纸 / 宗教用品**

---

### 🛒 Sales Tax 10% — 最常见

**饮料**：
- 软饮料（Coca-Cola, 100Plus, Sprite）
- 即饮咖啡 / 奶茶（Nescafé Can, Old Town）
- 果汁（Yeo's, Marigold）
- 瓶装水（Spritzer, Cactus）
- 能量饮料（Red Bull, Livita）

**加工食品 / 零食**：
- 即食面（Maggi, Cintan, Indomie, MyKuali）
- 饼干（Julie's, Jacob's, Oreo）
- 薯片（Mamee Double Decker, Twisties, Jack 'n Jill）
- 糖果 / 巧克力（Cadbury, KitKat, Beryl's）
- 冰淇淋（Walls, Magnolia, Magnum）
- 面包（Gardenia, High 5, Massimo）
- 调味料（Maggi 酱料、Kikkoman 酱油、辣椒酱）

**日用品 / 个人护理**：
- 牙膏 / 牙刷（Darlie, Colgate, Sensodyne, Oral-B）
- 洗发水 / 护发素（Pantene, Head & Shoulders, Sunsilk）
- 沐浴露 / 肥皂（Lifebuoy, Dettol, Dove）
- 香体剂（Rexona, Nivea）
- 护肤品（Olay, Nivea, Garnier）
- 纸巾 / 湿巾（Premier, Kleenex）
- 卫生巾 / 尿布（Laurier, Sofy, Mamypoko）

**清洁用品**：
- 洗衣液 / 洗衣粉（Dynamo, Breeze, Top, Attack）
- 洗洁精（Sunlight）
- 漂白剂 / 消毒液（Clorox, Lizol）
- 空气清新剂（Glade）
- 马桶清洁（Harpic）

**电子产品 / 家电**：
- 风扇 / 电饭煲（Khind, Milux, Pensonic）
- 小家电（Philips, Panasonic, Sharp）

**文具 / 办公用品**：
- 笔 / 笔记本（Campap, Faber-Castell）
- 胶水 / 胶带（UHU, Scotch）

---

### ☕ Service Tax 6% — 服务类（Demo SKU 不涉及）

Demo 以实物商品为主，Service Tax 6% 基本用不到。若需要生成服务型"SKU"（如 Installation Fee, Delivery Fee, Consultation Fee），使用 `SST-6`。

---

## 判断决策树（生成 seed 时自动分类）

```
SKU 名称 / 类别 → 判断 SST
│
├─ 含"mg | capsule | tablet | syrup | cream | Panadol | Strepsils | Vicks | 维生素" → SST-0 EXEMPT
├─ 是"大米 | 食用油 | 面粉 | 糖 | 盐 | 鸡蛋 | 书籍 | 婴儿配方奶粉" → SST-0 EXEMPT
├─ 是"安装费 | 配送费 | 咨询费 | 服务费" → SST-6
└─ 其他（默认大部分商品） → SST-10
```

---

## 常见错误（Seed 时避免）

| 商品 | ❌ 常错 | ✅ 正确 | 理由 |
|---|---|---|---|
| Milo 3-in-1 | EXEMPT | SST-10 | 加工饮料粉（不是新鲜食品） |
| Nescafé（罐装） | EXEMPT | SST-10 | 加工饮料 |
| Dutch Lady 调味牛奶 | EXEMPT | SST-10 | 调味加工（非纯鲜奶） |
| Dutch Lady UHT 纯鲜奶 | SST-10 | EXEMPT | 基本食品 |
| Panadol | SST-10 | EXEMPT | OTC 药品 |
| Baby Formula 婴儿奶粉 | SST-10 | EXEMPT | 婴幼儿基本食品 |
| Nike 鞋 | EXEMPT | SST-10 | 服装不 exempt |
| Gardenia 面包 | EXEMPT | SST-10 | 加工烘焙 |
| Jasmine 大米 | SST-10 | EXEMPT | 基本食品 |
| Camel 食用油 | SST-10 | EXEMPT | 基本食品 |

---

## 权威来源（实际项目需对照更新）

- Kastam SST Act 2018
- Ministry of Finance 豁免清单（Order 2022）
- LHDN e-Invoice Specific Guideline 附录 D（常见税码映射）
