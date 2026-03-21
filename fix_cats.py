"""
categories.py'deki KATEGORILER dict'ini kontrol et ve düzelt.
Sorun: eski dict kapandıktan SONRA yeni kategoriler eklendi.
Çözüm: eski dict'in kapanış } satırını bul, ondan ÖNCE yeni kategorileri ekle.
"""
content = open('app/routes/categories.py', encoding='utf-8-sig').read()

# Eski KATEGORILER dict'inin sonu — "tesettur" bloğundan sonra gelen } satırı
# Yeni kategorilerin başı — "guzellik-estetik"
new_cats_start = content.find('    "guzellik-estetik": {')
old_dict_end   = content.rfind('\n}\n\n# ─── ROUTES', 0, new_cats_start)

print(f"new_cats_start: {new_cats_start}")
print(f"old_dict_end:   {old_dict_end}")

if new_cats_start == -1 or old_dict_end == -1:
    print("Beklenen pozisyon bulunamadı!")
    exit(1)

# old_dict_end konumundaki \n}\n\n# ─── bölümünü bul
# Buradaki } KATEGORILER dict'inin kapanışı — bunu kaldır, yeni kategoriler zaten sonrasında
# Yani: eski_dict_kapanisi + yeni_kategoriler + # ROUTES şeklinde

# Parçala
before  = content[:old_dict_end]          # KATEGORILER = { ... tesettur sonu },'
middle  = content[new_cats_start:]        # "guzellik-estetik": { ... } \n}\n\n# ROUTES ...

# middle'daki ilk }\n\n# ─── ROUTES öncesini al (yeni kategoriler)
routes_marker = '\n}\n\n# ─── ROUTES'
routes_pos = middle.find(routes_marker)
new_cats_block = middle[:routes_pos]      # tüm yeni kategoriler (} kapanışı olmadan)
rest           = middle[routes_pos:]      # \n}\n\n# ─── ROUTES ...

# Yeni içerik: before + virgül + new_cats_block + rest
new_content = before + ',\n' + new_cats_block + rest

open('app/routes/categories.py', 'w', encoding='utf-8').write(new_content)
print("Düzeltme tamamlandı!")

# Doğrulama
import sys
sys.path.insert(0, '.')
# Parse kontrolü
compile(new_content, 'categories.py', 'exec')
print("Syntax OK!")
