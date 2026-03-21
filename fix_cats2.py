c = open('app/routes/categories.py', encoding='utf-8-sig').read()

# KATEGORILER dict'inin kapanış } pozisyonunu bul (brace sayarak)
kat_start = c.find('KATEGORILER = {')
depth = 0
in_string = False
string_char = None
kat_end = -1
for i, ch in enumerate(c[kat_start:], kat_start):
    if in_string:
        if ch == string_char and c[i-1] != '\\':
            in_string = False
    else:
        if ch in ('"', "'"):
            in_string = True
            string_char = ch
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                kat_end = i
                break

print(f"KATEGORILER ends at: {kat_end}")

# Yeni kategorilerin bloğunu bul (guzellik-estetik'ten ROUTES'a kadar)
new_cats_marker = '    "guzellik-estetik": {'
routes_marker   = '# ─── ROUTES'

new_cats_start = c.find(new_cats_marker)
routes_start   = c.find(routes_marker)

print(f"new_cats_start: {new_cats_start}")
print(f"routes_start: {routes_start}")

# Yeni kategoriler bloğu (son } ve boş satırlar hariç)
new_cats_block = c[new_cats_start:routes_start].rstrip()
# Sondaki '}' kapat satırını kaldır
if new_cats_block.endswith('}'):
    new_cats_block = new_cats_block[:-1].rstrip()

print(f"new_cats_block length: {len(new_cats_block)}")

# Yeni içeriği oluştur:
# 1. KATEGORILER başından kat_end'e kadar (} hariç)
# 2. , + yeni kategoriler
# 3. } (KATEGORILER kapanışı)
# 4. Geri kalan (HIZMETLER + ROUTES vs) - ama new_cats_block kısmı olmadan

before_kat_close = c[kat_start:kat_end]  # KATEGORILER = { ... son kategori },
after_kat        = c[kat_end+1:]          # \n\nHIZMETLER = { ... + new_cats_block + ROUTES

# after_kat'tan new_cats_block'u kaldır
# new_cats_block + kapanış } + ROUTES arası
remove_start = after_kat.find('    "guzellik-estetik":')
remove_end   = after_kat.find('# ─── ROUTES')
# remove_start'tan remove_end'e kadar sil
after_clean = after_kat[:remove_start] + after_kat[remove_end:]

# Yeni içerik
new_content = (
    before_kat_close +          # KATEGORILER = { ... eski son entry },
    ',\n' +                      # virgül
    new_cats_block +             # yeni kategoriler
    '\n}\n' +                    # KATEGORILER kapanışı
    after_clean                  # HIZMETLER + ROUTES (temiz)
)

open('app/routes/categories.py', 'w', encoding='utf-8').write(new_content)
print("Yazildi!")

# Syntax kontrolü
try:
    compile(new_content, 'categories.py', 'exec')
    print("SYNTAX OK!")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
