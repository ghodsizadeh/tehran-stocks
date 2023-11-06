from enum import Enum, unique


@unique
class IndustryGroup(Enum):
    def __init__(self, code, farsi_name):
        self._value_ = code
        self.farsi_name = farsi_name

    AGRICULTURE = (1, "زراعت و خدمات وابسته")
    FORESTRY_FISHING = (2, "جنگلداري و ماهيگيري")
    COAL_MINING = (10, "استخراج زغال سنگ")
    OIL_GAS_EXTRACTION = (11, "استخراج نفت گاز و خدمات جنبي جز اكتشاف")
    METAL_ORE_MINING = (13, "استخراج كانه هاي فلزي")
    OTHER_MINING = (14, "استخراج ساير معادن")
    REMOVED_FOOD_BEVERAGE = (15, "حذف شده- فرآورده‌هاي غذايي و آشاميدني")
    TEXTILES = (17, "منسوجات")
    LEATHER_FOOTWEAR = (19, "دباغي، پرداخت چرم و ساخت انواع پاپوش")
    WOOD_PRODUCTS = (20, "محصولات چوبي")
    PAPER_PRODUCTS = (21, "محصولات كاغذي")
    PUBLISHING_PRINTING = (22, "انتشار، چاپ و تكثير")
    OIL_COAL_NUCLEAR = (23, "فراورده هاي نفتي، كك و سوخت هسته اي")
    REMOVED_CHEMICALS = (24, "حذف شده-مواد و محصولات شيميايي")
    RUBBER_PLASTIC = (25, "لاستيك و پلاستيك")
    COMPUTER_ELECTRONIC_OPTICAL = (26, "توليد محصولات كامپيوتري الكترونيكي ونوري")
    BASIC_METALS = (27, "فلزات اساسي")
    METAL_PRODUCTS = (28, "ساخت محصولات فلزي")
    MACHINERY_EQUIPMENT = (29, "ماشين آلات و تجهيزات")
    ELECTRICAL_MACHINERY = (31, "ماشين آلات و دستگاه‌هاي برقي")
    COMMUNICATION_DEVICES = (32, "ساخت دستگاه‌ها و وسايل ارتباطي")
    MEDICAL_OPTICAL_MEASURING = (33, "ابزارپزشكي، اپتيكي و اندازه‌گيري")
    AUTOMOTIVE_PARTS = (34, "خودرو و ساخت قطعات")
    OTHER_TRANSPORT_DEVICES = (35, "ساير تجهيزات حمل و نقل")
    FURNITURE_OTHER = (36, "مبلمان و مصنوعات ديگر")
    SUGAR = (38, "قند و شكر")
    MULTI_SECTOR_INDUSTRIAL = (39, "شركتهاي چند رشته اي صنعتي")
    ELECTRICITY_GAS_STEAM_HOT_WATER = (40, "عرضه برق، گاز، بخاروآب گرم")
    WATER_TREATMENT_DISTRIBUTION = (41, "جمع آوري، تصفيه و توزيع آب")
    FOOD_BEVERAGE_EXCEPT_SUGAR = (42, "محصولات غذايي و آشاميدني به جز قند و شكر")
    PHARMACEUTICALS = (43, "مواد و محصولات دارويي")
    CHEMICAL_PRODUCTS = (44, "محصولات شيميايي")
    INDUSTRIAL_CONTRACTING = (45, "پيمانكاري صنعتي")
    WHOLESALE_EXCEPT_VEHICLES = (46, "تجارت عمده فروشي به جز وسايل نقليه موتور")
    RETAIL_EXCEPT_VEHICLES = (47, "خرده فروشي،باستثناي وسايل نقليه موتوري")
    CERAMICS = (49, "كاشي و سراميك")
    TRADE_VEHICLES = (50, "تجارت عمده وخرده فروشي وسائط نقليه موتور")
    AIR_TRANSPORT = (51, "حمل و نقل هوايي")
    STORAGE_TRANSPORT_SUPPORT = (52, "انبارداري و حمايت از فعاليتهاي حمل و نقل")
    CEMENT_LIME_PLASTER = (53, "سيمان، آهك و گچ")
    OTHER_NON_METALLIC_MINERALS = (54, "ساير محصولات كاني غيرفلزي")
    HOTELS_RESTAURANTS = (55, "هتل و رستوران")
    INVESTMENTS = (56, "سرمايه گذاريها")
    BANKS_CREDIT_INSTITUTIONS = (57, "بانكها و موسسات اعتباري")
    OTHER_FINANCIAL_INTERMEDIARIES = (58, "ساير واسطه گريهاي مالي")
    PRIORITY_RIGHTS_HOUSING = (59, "اوراق حق تقدم استفاده از تسهيلات مسكن")
    TRANSPORT_STORAGE_COMMUNICATIONS = (60, "حمل ونقل، انبارداري و ارتباطات")
    WATER_TRANSPORT = (61, "حمل و نقل آبي")
    TRANSPORT_SUPPORT = (63, "فعاليت هاي پشتيباني و كمكي حمل و نقل")
    TELECOMMUNICATIONS = (64, "مخابرات")
    FINANCIAL_MONETARY_INTERMEDIARIES = (65, "واسطه‌گري‌هاي مالي و پولي")
    INSURANCE_PENSION_FUND = (66, "بيمه وصندوق بازنشستگي به جزتامين اجتماعي")
    AUXILIARY_FINANCIAL_INSTITUTIONS = (67, "فعاليتهاي كمكي به نهادهاي مالي واسط")
    NEGOTIABLE_INVESTMENT_FUND = (68, "صندوق سرمايه گذاري قابل معامله")
    FINANCIAL_SECURITIES = (69, "اوراق تامين مالي")
    REAL_ESTATE = (70, "انبوه سازي، املاك و مستغلات")
    ENGINEERING_TECHNICAL_ANALYSIS = (71, "فعاليت مهندسي، تجزيه، تحليل و آزمايش فني")
    COMPUTER_RELATED_ACTIVITIES = (72, "رايانه و فعاليت‌هاي وابسته به آن")
    INFORMATION_COMMUNICATIONS = (73, "اطلاعات و ارتباطات")
    TECHNICAL_ENGINEERING_SERVICES = (74, "خدمات فني و مهندسي")
    INTELLECTUAL_PROPERTY_SECURITIES = (76, "اوراق بهادار مبتني بر دارايي فكري")
    RENTING_LEASING = (77, "فعالبت هاي اجاره و ليزينگ")
    ADMINISTRATIVE_SUPPORT = (82, "فعاليت پشتيباني اجرائي اداري وحمايت كسب")
    ART_ENTERTAINMENT_CREATIVE = (90, "فعاليت هاي هنري، سرگرمي و خلاقانه")
    CULTURAL_SPORTS = (93, "فعاليتهاي فرهنگي و ورزشي")
    INACTIVE_SECURITIES = (98, "گروه اوراق غيرفعال")
    INDEX = ("X1", "شاخص")
